#!/bin/bash

# Network recording for piTelex

if [ -n "$1" ]; then
	PITELEX_PORT="$1"
else
	# Try extracting port number from configuration
	PITELEX_PORT=$(sed -n -e 's/^.*\s"port":\s*\(.*\),/\1/p' telex.json ../telex.json 2>/dev/null)
	if [ -z $PITELEX_PORT ]; then
		echo "Error: piTelex port could not be read (try calling me with the port as parameter)"
		exit 1
	fi
fi
echo "Starting capture on TCP port \"$PITELEX_PORT\" ..."
tshark -i wlan0 -f "tcp port $PITELEX_PORT" -w "pitelex-$(date --iso-8601=s).pcapng" -P
