# mar/18/2014 09:25:34 by RouterOS 6.10
# software id = WLVA-21HW
#


/ip service set port=9080 numbers=[/ip service find name=www] address=10.199.0.0/22
/ip service set port=9021 numbers=[/ip service find name=ftp] address=10.199.0.0/22
/ip service set port=9022 numbers=[/ip service find name=ssh] address=10.199.0.0/22
/ip service set numbers=[/ip service find name=api] address=10.199.0.0/22
/ip service set numbers=[/ip service find name=api-ssl] address=10.199.0.0/22
/ip service disable numbers=[/ip service find name=telnet]
/ip service disable numbers=[/ip service find name=winbox]
