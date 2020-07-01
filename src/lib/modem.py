import time
from network import LTE


def _send_at_cmd(lte: LTE, cmd: str) -> []:
    result = []
    for _ in range(3):
        print("++ " + cmd)
        result = [k for k in lte.send_at_cmd(cmd).split('\r\n') if len(k.strip()) > 0]
        print('-- ' + '\r\n-- '.join([r for r in result]))

        if result[-1] == 'OK':
            print()
            break
        else:
            time.sleep(0.2)

    return result


def set_modem_func_lvl(lte: LTE, func_lvl: int):
    """
    Sets modem to the desired level of functionality
    Throws exception if operation fails.
    :param func_lvl: the functionality level (0: minimum,
                                              1: full,
                                              4: disable modem both transmit and receive RF circuits)
    """
    get_func_cmd = "AT+CFUN?"
    set_func_cmd = "AT+CFUN={}".format(func_lvl)

    print("\n>> setting up modem")

    # check if modem is already set to the correct functionality level
    result = _send_at_cmd(lte, get_func_cmd)
    if result[-1] == 'OK' and result[-2] == '+CFUN: {}'.format(func_lvl):
        return

    # set modem functionality level
    result = _send_at_cmd(lte, set_func_cmd)
    if result[-1] == 'OK':
        # check if modem is set and ready
        result = _send_at_cmd(lte, get_func_cmd)
        if result[-1] == 'OK' and result[-2] == '+CFUN: {}'.format(func_lvl):
            return

    raise Exception("setting up modem failed: {}".format(repr(result)))


def get_imsi(lte: LTE) -> str:
    """
    Get the international mobile subscriber identity (IMSI) from SIM
    """
    IMSI_LEN = 15
    get_imsi_cmd = "AT+CIMI"

    print("\n>> getting IMSI")
    result = _send_at_cmd(lte, get_imsi_cmd)
    if result[-1] == 'OK' and len(result[0]) == IMSI_LEN:
        return result[0]

    raise Exception("getting IMSI failed: {}".format(repr(result)))
