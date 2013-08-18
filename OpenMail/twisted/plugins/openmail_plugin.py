# myapp

from twisted.application.service import ServiceMaker

OpenMail = ServiceMaker(
    "OpenMail",
    "openmail.mytap",
    "A k-v db based email service",
    "openmail")
