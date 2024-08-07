# Get e-mail notification on new telex

### Motivation

Sometimes a new telex may arrive on one of the teleprinters without you noticing it. For example, because the teleprinters are in the basement due to noise or because you are not at home but on the road or in the office.
This small script informs you by e-mail about new telexes and optionally also provides the content of the telex.

It works under Debian-based linux distributions.

### Prerequisites

* Install some dependencies:

      sudo apt install sendemail inotify-tools libio-socket-ssl-perl libnet-ssleay-perl

> [!IMPORTANT]
> Debian 12 (bookworm) based systems using version 2.08* of `libio-socket-ssl-perl`: 
>
>      sudo apt install sendemail inotify-tools libio-socket-ssl-perl libnet-ssleay-perl libinotifytools0 perl-openssl-abi-3 libio-socket-inet6-perl libsocket6-perl
>
>
> File `/usr/share/perl5/IO/Socket/SSL.pm` has a modification which is incompatible with `sendemail` if SSL is enabled.
>
> Workaraound:
> * Either switch off SSL ( `sendemail`-option `-o TLS:off`) (not recommended since most mailers require SSL/TLS)
>
> * or use the package `libio-socket-ssl-perl` shipped with Debian 11 (bullseye). A functional version of the package is included in the subdirectory `mail-notify` for convenience :)
>
>       sudo dpkg -i libio-socket-ssl-perl_2.074-2_all.deb
>
>   To avoid overwriting this package by future upgrade operations, you may consider pinning the version of the package:
> 
>       sudo apt-mark hold libio-socket-ssl-perl

### Installation and Configuration

* Look for a subdirectory of piTelex called `mail-notify` and change to it. 
* Make the script file executable:
       
       chmod +x ...mail-notify/txnotify.sh 

* Replace the dummy contents of the e-mail related variables in the file with functional settings.
* If you want to receive the full telex message text via email, set `MSG=yes`, leave it at the default (empty) otherwise.
* Set `WATCH` to the path of the piTelex archive directory
* Check that the archive module is enabled in piTelex and working, for the script relies on the archive messages of piTelex.
* Ensure that the user account which runs the script has read access to the `WATCH`-directory and the files therein.
> [!TIP]
> If the script doesn't work as expected, edit the source code and delete the two "-q" Options temporarily. This makes the output more verbose and helps to find the mistake, hopefully.

### Auto start at boot time
* To start the script automatically at system boot, edit `/etc/rc.local` as root user (`sudo nano /etc/rc.local`) and **before** the line `exit 0` add a line like:

       /path/to/txnotify.sh 2>&1 &

  Take care to copy the redirections and ampersands correctly. After rebooting, check if the script is running:

      $ ps ax | grep notify
        628 ?        S      0:00 /bin/bash /home/pi/piTelex-utils/txnotify.sh
        630 ?        S      0:00 inotifywait -q -m /home/pi/piTelex-archive -e create
        631 ?        S      0:00 /bin/bash /home/pi/piTelex-utils/txnotify.sh
   
