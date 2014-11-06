import os
from postmark import PMMail


def prod_error_instant_mail(error_num, object, details, critical_level="INFO"):
    prod_error_mail(error_num, object, details, critical_level)


def prod_error_notif_mail(error_num, object, details, critical_level="INFO"):
    prod_error_mail(error_num, object, details, critical_level, server="NOTIF-ERR")


def prod_error_mail(error_num, object, details, critical_level=0, server="INSTANT-ERR"):
    message = PMMail(
        api_key=os.environ.get('POSTMARK_API_KEY'),
        subject="[{}] [{}] [#{}] {}".format(server, critical_level, error_num, object),
        sender="dev@pictever.com",
        to="dev@pictever.com",
        text_body=details,
        tag="")

    print "[{}] [{}] [#{}] {}".format(server, critical_level, error_num, object),
    message.send()

  