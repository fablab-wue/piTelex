#!/bin/bash
#
# For Debian based linux distros
#
# tool to monitor a directory for new files 
# and send notification to an email address
# when new files arrive
#
# depends on packages (install with "apt install ..."):
#    sendemail
#    inotify-tools
#    libio-socket-ssl-perl
#    libnet-ssleay-perl
#
# =========================================================
# in telex.json, archive module must be enabled and working
# =========================================================
#
#
#
# =========================================================
# for autostart at system boot, edit /etc/rc.local and add 
# *before* the "exit" line:
# ---------------------------------------------------------
#   # Monitor for new telex and send notification email
#   /path/to/notify-new-telex.sh 2>&1 &
# ---------------------------------------------------------
# Be sure to insert the correct path to the script
# and copy the ampersands and redirections correctly!
# =========================================================
#
#
# Now set some variables for mail transport:
#
WATCH="/home/pi/piTelex-archive" 	# Directory where piTelex puts messages
					#   must correspond to the archive path 
					#   in telex.json
FM="telex@mailprovider.de"		# From Address
TO="toaddress@maildomain.de"		# destination mailaddress 
U="username@mailprovider.de"		# user
P="password für $U "			# password
S="smtphost.mailprovider.de:port"	# mailhost and port
MSG=''					# wether or not to attach the
					#   telex content to the mail
					#   anything but '' means "yes"
##############################################################################

HOST=`hostname`
inotifywait -q -m $WATCH -e create  |  
    while read dir action file; do
	received=`echo "$file" | grep from`
	if [ "$received" ] ; then
		if [ $MSG ] ; then 
 			TEXT=`cat ${dir}"${file}" | sed -e s/\>//g | sed -e s/\<//g`
		else
			TEXT="$received"
		fi
		sendemail -q -f "$FM" -t "$TO" -xu "$U" -xp "$P" -s "$S" -u "New telex message arrived at $HOST" -m "$TEXT" 
	fi

    done
