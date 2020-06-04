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

        time.sleep(0.2)

    return result


def get_imsi(lte: LTE) -> str:
    """
    Get the international mobile subscriber identity (IMSI) of the SIM card
    """
    IMSI_LEN = 15
    get_imsi_cmd = "AT+CIMI"

    print("\n>> getting IMSI")
    result = _send_at_cmd(lte, get_imsi_cmd)
    if result[-1] == 'OK' and len(result[0]) == IMSI_LEN:
        return result[0]

    raise Exception("getting IMSI failed: {}".format(repr(result)))
