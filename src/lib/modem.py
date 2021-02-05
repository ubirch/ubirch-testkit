from network import LTE

from error_handling import *

COLOR_MODEM_FAIL = LED_PINK_BRIGHT


class LTEunsolQ(LTE):
    """
    Extends LTE with handling of unsolicited responses.
    """

    def __init__(self, error_handler: ErrorHandler = None, *args, **kwargs):
        """
        Initialize with error handler.
        :param debug: FIXME
        """
        super().__init__(*args, **kwargs)
        self.error_handler = error_handler

    def send_at_cmd(self, cmd: str, expected_result_prefix: str = None,
                    debug_print: bool = False) -> str:
        """
        Sends AT command. This function extends the `send_at_command` method of
        LTE. It additionally filters its output for unsolicited messages.
        :param cmd: command to send
        :param expected_result_prefix: the return value of LTE.send_at_cmd is
            parsed by this value, if None it is extracted from the command
        :param debug_print: debug output flag
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

        if debug_print:
            print("++ {} -> expect result prefixed with \"{}\"."
                  .format(cmd, expected_result_prefix))

        result = [k for k in super().send_at_cmd(cmd).split('\r\n')
                  if len(k.strip()) > 0]
        if debug_print:
            print('-- ' + '\r\n-- '.join([r for r in result]))

        retval = None

        # filter results
        skip_next_line = False
        for line_number, line in enumerate(result):
            if skip_next_line:
                continue
            if line == "OK":
                retval = line
            elif line.startswith("ERROR"):
                pass
            elif line.startswith("+CME ERROR") or line.startswith("+CMS ERROR"):
                retval = line
            elif line.startswith(expected_result_prefix):
                if line_number + 1 < len(result):
                    if result[line_number + 1] == "OK":
                        retval = line
                    skip_next_line = True
                else:
                    retval = line
            else:
                # unsolicited
                if self.error_handler is not None:
                    self.error_handler.log("WARNING: ignoring: {}".format(line), COLOR_MODEM_FAIL)

        return retval


def reset_modem(lte: LTEunsolQ, debug_print=False):
    function_level = "1"

    if debug_print: print("\twaiting for reset to finish")
    lte.reset()
    lte.init()

    if debug_print: print("\tsetting function level")
    for _ in range(15):
        result = lte.send_at_cmd("AT+CFUN=" + function_level,
                                 debug_print=debug_print)
        time.sleep(0.2)
        if result is not None:
            break
    else:
        raise Exception("could not set modem function level")
    for _ in range(15):
        result = lte.send_at_cmd("AT+CFUN?",
                                 debug_print=debug_print)
        time.sleep(0.2)
        if result == "+CFUN: " + function_level:
            break
    else:
        raise Exception("could not get modem function level")

    if debug_print: print("\twaiting for SIM to be responsive")
    for _ in range(30):
        if lte.send_at_cmd("AT+CIMI", expected_result_prefix="",
                           debug_print=debug_print) is not None:
            break
        time.sleep(0.2)
    else:
        raise Exception("SIM does not seem to respond after reset")


def get_imsi(lte: LTEunsolQ, debug_print=False) -> str:
    """
    Get the international mobile subscriber identity (IMSI) of the SIM card
    """
    IMSI_LEN = 15
    get_imsi_cmd = "AT+CIMI"

    if debug_print: print("\n>> getting IMSI")
    for _ in range(3):
        result = lte.send_at_cmd(get_imsi_cmd, expected_result_prefix="",
                                 debug_print=debug_print)
        if result is not None and len(result) == IMSI_LEN:
            return result
        time.sleep(0.2)

    raise Exception("getting IMSI failed: {}".format(repr(result)))  # fixme result can be 'None'


def get_signalquality(lte: LTEunsolQ, debug_print=False) -> str:
    """
    Get received signal quality parameters.
    """

    get_signalquality_cmd = "AT+CESQ"
    if debug_print:
        print("\n>> getting signal quality")
    for _ in range(3):
        result = lte.send_at_cmd(get_signalquality_cmd,
                                 debug_print=debug_print)
        if result is not None:
            break
        time.sleep(0.2)
    else:
        raise Exception("getting signal quality failed")

    result = result.split(',')
    # +CESQ: <rxlev>,<ber>,<rscp>,<ecno>,<rsrq>,<rsrp>
    return "RSRQ: {}, RSRP: {}".format(result[4], result[5])
