# Changes since release 2025-12


### New module "StartMsg" 
Print some diagnostics after startup of piTelex. Documentation see 
https://github.com/fablab-wue/piTelex/blob/testing/doc/SW_StartMsg.md

### CLI commands updated and cleared
Some commands had to be removed.

```text
available·commands:                                                  
help,·?········-·show·this·help                                      
cpu············-·show·cpu·load                                       
dev,·devices···-·list·enabled·devices                                
disk···········-·show·root·filesystem·usage                          
ip·············-·list·local·interfaces·and·ipv4·addresses            
ipx············-·show·external·(wan)·ipv4·address                    
kg,·wru········-·show·wru·id                                         
lupd···········-·linux·system·update·(apt-get·update/upgrade)        
mem············-·show·memory·usage                                   
ping···········-·ping·8.8.8.8,·(4·packets)                           
port···········-·show·i-telex·port·(if·configured)                   
uptime·········-·show·system·uptime                                  
w··············-·show·logged·in·users                                
whoami·········-·identify·this·cli                                   
wlan···········-·scan·wlan·networks                                  
wps············-·connect·wlan·via·wps                                
reboot·········-·reboot·system                                       
shutdown·······-·shutdown·system                                     
exit···········-·exit·cli
```
