import time
from network import LTE
from error_handling import ErrorHandler, COLOR_MODEM_FAIL


class LTEunsolQ(LTE):
    """
    Extends LTE with handling of unsolicited responses.
    """

    def __init__(self, error_handler : ErrorHandler = None, *args, **kwargs):
        """
        Initialize with error handler.
        :param debug: FIXME
        """
        super().__init__(*args, **kwargs)
        self.error_handler = error_handler

    def send_at_cmd(self, cmd: str, expected_result_prefix : str = None,
                    debug_print : bool = False) -> str:
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

        split_result_by_colon = False
        if expected_result_prefix is None:
            split_result_by_colon = True
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
        l_result = len(result)
        ll = 0
        while ll < l_result:
            if result[ll] == "OK":
                retval = result[ll]
            elif result[ll].startswith("ERROR"):
                pass
            elif result[ll].startswith("+CME ERROR") or result[ll].startswith("+CMS ERROR"):
                retval = result[ll]
            elif result[ll].startswith(expected_result_prefix):
                if (ll + 1 < l_result):
                    if result[ll+1] == "OK":
                        retval = result[ll]
                    ll += 1
                else:
                    retval = result[ll]
            else:
                # unsolicited
                if self.error_handler is not None:
                    self.error_handler.log("WARNING: ignoring: {}".format(result[ll]),
                                           COLOR_MODEM_FAIL)
            ll += 1

        return retval


def _send_at_cmd(lte: LTE, cmd: str, debug_print=True) -> []:
    result = []
    for _ in range(3):
        if debug_print: print("++ " + cmd)
        result = [k for k in lte.send_at_cmd(cmd).split('\r\n') if len(k.strip()) > 0]
        if debug_print: print('-- ' + '\r\n-- '.join([r for r in result]))

        if result[-1] == 'OK':
            if debug_print: print()
            break

        time.sleep(0.2)

    return result


def reset_modem(lte: LTE, debug_print=False):
    function_level = "1"
    cereg_level = "2"

    if debug_print: print("\twaiting for reset to finish")
    lte.reset()
    lte.init()

    if debug_print: print("\tsetting function level")
    for tries in range(5):
        _send_at_cmd(lte, "AT+CFUN=" + function_level, debug_print=debug_print)
        result = _send_at_cmd(lte, "AT+CFUN?", debug_print=debug_print)
        if result[0] == '+CFUN: ' + function_level:
            break
    else:
        raise Exception("could not set modem function level")

    if debug_print: print("\twaiting for SIM to be responsive")
    for tries in range(10):
        result = _send_at_cmd(lte, "AT+CIMI", debug_print=debug_print)
        if result[-1] == 'OK':
            break
    else:
        raise Exception("SIM does not seem to respond after reset")

    if debug_print: print("\tdisabling CEREG messages")
    # we disable unsolicited CEREG messages, as they interfere with AT communication with the SIM via CSIM commands
    # this also requires to use an attach method that does not require cereg messages, for pycom that is legacyattach=false
    for tries in range(5):
        _send_at_cmd(lte, "AT+CEREG=" + cereg_level, debug_print=debug_print)
        result = _send_at_cmd(lte, "AT+CEREG?", debug_print=debug_print)
        if result[0][0:9] == '+CEREG: ' + cereg_level:
            break
    else:
        raise Exception("could not set CEREG level")


def get_imsi(lte: LTE, debug_print=False) -> str:
    """
    Get the international mobile subscriber identity (IMSI) of the SIM card
    """
    IMSI_LEN = 15
    get_imsi_cmd = "AT+CIMI"

    if debug_print: print("\n>> getting IMSI")
    result = _send_at_cmd(lte, get_imsi_cmd, debug_print=debug_print)
    if result[-1] == 'OK' and len(result[0]) == IMSI_LEN:
        return result[0]

    raise Exception("getting IMSI failed: {}".format(repr(result)))

def get_signalquality(lte: LTE, debug_print=False) -> str:
    """
    Get received signal quality parameters.
    """
    get_signalquality_cmd = "AT+CESQ"
    if debug_print:
        print("\n>> getting signal quality")
    for _ in range(3):
        result = lte.send_at_cmd_new(get_signalquality_cmd,
                                     debug_print=debug_print)
        if result is None:
            break
    if result is None:
        raise Exception("getting signal quality failed")

    raise Exception("getting signal quality failed: {}".format(repr(result)))



        return retval
