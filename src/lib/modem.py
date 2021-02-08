from error_handling import *
from network import LTE
from ubirch import ModemInterface

COLOR_MODEM_FAIL = LED_PINK_BRIGHT


class Modem(ModemInterface):
    """
    todo
    """

    def __init__(self, lte: LTE, error_handler: ErrorHandler = None, debug: bool = False):
        """
        Initialize with error handler.
        :param debug: todo
        """
        self.lte = lte
        self._AT_session_active = False  # weather or not the lib currently opened an AT commands session
        self._AT_session_modem_suspended = False  # weather the modem was suspended for an AT session
        self.debug = debug
        self.error_handler = error_handler

    def prepare_AT_session(self) -> None:
        """
        Ensures all prerequisites to send AT commands to modem and saves the modems state
        for restoring it later.
        """
        if self._AT_session_active:
            return

        # if modem is connected, suspend it and remember that we did
        if self.lte.isconnected():
            self.lte.pppsuspend()
            self._AT_session_modem_suspended = True

        self._AT_session_active = True

    def finish_AT_session(self) -> None:
        """
        Restores the modem state after the library is finished sending AT commands.
        """
        if not self._AT_session_active:
            return

        # if modem was suspended for the session, restore it
        if self._AT_session_modem_suspended:
            self.lte.pppresume()
            self._AT_session_modem_suspended = False

        self._AT_session_active = False

    def check_sim_access(self) -> bool:
        """
        Checks Generic SIM Access.
        :return: if SIM access was successful
        """
        for _ in range(3):
            time.sleep(0.2)
            result = self.send_at_cmd("AT+CSIM=?")
            if result == "OK":
                return True

        return False

    def send_at_cmd(self, cmd: str, expected_result_prefix: str = None) -> str:
        """
        Sends AT command. This function extends the `send_at_command` method of
        LTE. It additionally filters its output for unsolicited messages.
        :param cmd: command to send
        :param expected_result_prefix: the return value of LTE.send_at_cmd is
            parsed by this value, if None it is extracted from the command
        :return: response message, None if it was a general error or just
            unsolicited messages
        """
        at_prefix = "AT"
        if at_prefix not in cmd:
            raise Exception('use only for AT+ prefixed commands')

        if expected_result_prefix is None:
            if "=" in cmd:
                expected_result_prefix = cmd[len(at_prefix):].split('=', 1)[0]
            elif "?" in cmd:
                expected_result_prefix = cmd[len(at_prefix):].split('?', 1)[0]
            else:
                expected_result_prefix = cmd[len(at_prefix):]

        if self.debug:
            print("++ {} -> expect result prefixed with \"{}\"."
                  .format(cmd, expected_result_prefix))

        result = [k for k in self.lte.send_at_cmd(cmd).split('\r\n') if len(k.strip()) > 0]
        if self.debug:
            print('-- ' + '\r\n-- '.join([r for r in result]))

        retval = None

        # filter results
        skip_next_line = False
        for line_number, line in enumerate(result):
            if skip_next_line:
                skip_next_line = False
                continue
            if line == "OK":
                retval = line
            elif line.startswith("ERROR"):
                pass
            elif line.startswith("+CME ERROR") or line.startswith("+CMS ERROR"):
                retval = line
            elif line.startswith(expected_result_prefix):  # if we find the expected prefix
                if line_number + 1 < len(result):               # we check if there is a next line
                    if result[line_number + 1] == "OK":             # only if the next line is "OK"
                        retval = line                                   # the line with the expected prefix is the potential return value
                    skip_next_line = True                           # either way, we do not need to check the next line further
                else:                                           # if there is no next line
                    retval = line                                   # we return the line with the expected prefix
            else:
                # unsolicited
                if self.error_handler is not None:
                    self.error_handler.log("WARNING: ignoring: {}".format(line), COLOR_MODEM_FAIL)

        return retval

    def reset(self):
        function_level = "1"

        if self.debug: print("\twaiting for reset to finish")
        self.lte.reset()
        self.lte.init()

        if self.debug: print("\tsetting function level")
        for _ in range(15):
            result = self.send_at_cmd("AT+CFUN=" + function_level)
            time.sleep(0.2)
            if result is not None:
                break
        else:
            raise Exception("could not set modem function level")
        for _ in range(15):
            result = self.send_at_cmd("AT+CFUN?")
            time.sleep(0.2)
            if result == "+CFUN: " + function_level:
                break
        else:
            raise Exception("could not get modem function level")

        if self.debug: print("\twaiting for SIM to be responsive")
        for _ in range(30):
            if self.send_at_cmd("AT+CIMI", expected_result_prefix="") is not None:
                break
            time.sleep(0.2)
        else:
            raise Exception("SIM does not seem to respond after reset")

    def get_imsi(self) -> str:
        """
        Get the international mobile subscriber identity (IMSI) of the SIM card
        """
        IMSI_LEN = 15
        get_imsi_cmd = "AT+CIMI"

        if self.debug: print("\n>> getting IMSI")
        result = None
        for _ in range(3):
            result = self.send_at_cmd(get_imsi_cmd, expected_result_prefix="")
            if result is not None and len(result) == IMSI_LEN:
                try:
                    int(result)  # throws ValueError if IMSI has invalid syntax for integer with base 10
                except ValueError:
                    continue
                else:
                    return result
            time.sleep(0.2)

        raise Exception("getting IMSI failed: {}".format(repr(result)))

    def get_signalquality(self) -> str:
        """
        Get received signal quality parameters.
        """

        get_signalquality_cmd = "AT+CESQ"
        if self.debug:
            print("\n>> getting signal quality")
        for _ in range(3):
            result = self.send_at_cmd(get_signalquality_cmd)
            if result is not None:
                break
            time.sleep(0.2)
        else:
            raise Exception("getting signal quality failed")

        result = result.split(',')
        # +CESQ: <rxlev>,<ber>,<rscp>,<ecno>,<rsrq>,<rsrp>
        return "RSRQ: {}, RSRP: {}".format(result[4], result[5])
