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
#   /path/to/txnotify.sh 2>&1 &
# ---------------------------------------------------------
# Be sure to insert the correct path to the script
# and copy the ampersands and redirections correctly!
# =========================================================
#
#
# Now set some variables for mail transport:
#
WATCH="/home/pi/piTelex-archive"
#
FM="telex@mailprovider.de"           # from address
TO="toaddress@maildestination.de"    # to address
U="username@mailprovider.de"         # mail account data
P="password-for-$U"                  # mail account data
S="mailhost.mailprovider.de:port"    # mail account data
#
##  killfile holds senders (WRU ID's) to be ignored, one per line
##  
# killfile=/home/pi/piTelex/utils/mail-notify/sender-blacklist
#
MSG=yes   # wether or not to include the telex contents, 
          # anything but '' means yes
################################################################################

HOST=`hostname`
unset blacklist
if [ -v killfile ] ; then
	if [ -f "$killfile" ] ; then
		if [ -r "$killfile" -a -s "$killfile" ] ; then
			blacklist="$killfile"
		fi
	fi
fi

inotifywait -q -m $WATCH -e create  |  
    while read dir action file; do
	      received=`echo "$file" | grep from` # only received msgs
	      [ "$blacklist" ] && received=`echo "$received" | grep -v -f "$blacklist"`
	      if [ "$received" ] ; then
		        if [ $MSG ] ; then 
 			          TEXT=`cat ${dir}"${file}" | sed -e s/\>//g | sed -e s/\<//g`
		        else
			          TEXT="$received"
		       fi
		       sendemail -q -f "$FM" -t "$TO" -xu "$U" -xp "$P" -s "$S" -u "New telex message arrived at $HOST" -m "$TEXT" 
	     fi
   done
