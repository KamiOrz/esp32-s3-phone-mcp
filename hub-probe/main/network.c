#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "nvs_flash.h"
#include "esp_timer.h"
#include "mbedtls/base64.h"
#include "mbedtls/platform_util.h"
#include "cJSON.h"
#include "phone.h"
#include "command_tools.h"
#include "network_config.h"
static char ip[20];
static bool authorized(httpd_req_t *r){
 char auth[96];char expected[96];snprintf(expected,sizeof(expected),"Bearer %s",PHONE_API_TOKEN);
 if(httpd_req_get_hdr_value_str(r,"Authorization",auth,sizeof(auth))!=ESP_OK||strcmp(auth,expected)){httpd_resp_set_status(r,"401 Unauthorized");httpd_resp_sendstr(r,"Bearer token required");return false;}
 if(httpd_req_get_hdr_value_len(r,"Origin")){httpd_resp_set_status(r,"403 Forbidden");httpd_resp_sendstr(r,"Browser origins are not accepted");return false;}
 return true;
}
static cJSON *status_json(void){
 cJSON *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"ip",ip);cJSON_AddBoolToObject(j,"adb_connected",phone_result.connected);cJSON_AddNumberToObject(j,"uptime_seconds",esp_timer_get_time()/1000000);cJSON_AddStringToObject(j,"transport","S3 USB ADB / Wi-Fi HTTP");return j;
}
static esp_err_t json_send(httpd_req_t *r,cJSON *j){char *s=cJSON_PrintUnformatted(j);if(!s)return ESP_FAIL;httpd_resp_set_type(r,"application/json");esp_err_t e=httpd_resp_sendstr(r,s);cJSON_free(s);return e;}
static esp_err_t health(httpd_req_t *r){if(!authorized(r))return ESP_OK;cJSON *j=status_json();esp_err_t e=json_send(r,j);cJSON_Delete(j);return e;}
static esp_err_t get_mcp(httpd_req_t *r){if(!authorized(r))return ESP_OK;httpd_resp_set_status(r,"405 Method Not Allowed");httpd_resp_set_hdr(r,"Allow","POST");return httpd_resp_send(r,NULL,0);}
static void text_result(cJSON *root,const char *text,bool error){
 cJSON *result=cJSON_AddObjectToObject(root,"result");cJSON_AddBoolToObject(result,"isError",error);cJSON *a=cJSON_AddArrayToObject(result,"content"),*v=cJSON_CreateObject();cJSON_AddStringToObject(v,"type","text");cJSON_AddStringToObject(v,"text",text);cJSON_AddItemToArray(a,v);
}
static void command_result(cJSON *root){
 const char *marker="__S3_EXIT__";char *tail=strstr(phone_result.tail,marker);char *last=tail;
 while(tail){last=tail;tail=strstr(tail+1,marker);}
 int code=-1;bool known=false;if(last){char *end;long n=strtol(last+strlen(marker),&end,10);known=end!=last+strlen(marker)&&(*end=='\n'||*end=='\r'||!*end);if(known)code=(int)n;}
 char *found=strstr(phone_result.text,marker);if(found){char *next;while((next=strstr(found+1,marker)))found=next;if(found>phone_result.text&&found[-1]=='\n')found--;*found=0;}
 if(phone_result.truncated){size_t n=strlen(phone_result.text),start=n;while(start>0&&((unsigned char)phone_result.text[start-1]&0xc0)==0x80)start--;if(start>0){unsigned char lead=phone_result.text[start-1];size_t need=lead>=0xf0?4:lead>=0xe0?3:lead>=0xc0?2:1;if(n-start+1<need)phone_result.text[start-1]=0;}}
 text_result(root,phone_result.text, !known||code!=0);
 cJSON *result=cJSON_GetObjectItemCaseSensitive(root,"result"),*data=cJSON_AddObjectToObject(result,"structuredContent");
 cJSON_AddStringToObject(data,"output",phone_result.text);cJSON_AddBoolToObject(data,"exit_code_known",known);if(known)cJSON_AddNumberToObject(data,"exit_code",code);else cJSON_AddNullToObject(data,"exit_code");
 cJSON_AddBoolToObject(data,"truncated",phone_result.truncated);cJSON_AddNumberToObject(data,"bytes_received",phone_result.total_received);cJSON_AddNumberToObject(data,"elapsed_ms",phone_result.elapsed_ms);
 if(!known)cJSON_AddStringToObject(data,"warning","Shell exit marker was not received; do not assume success");
}
static esp_err_t image_result(httpd_req_t *r,cJSON *id){
 char *s=cJSON_PrintUnformatted(id);if(!s)return ESP_FAIL;
 httpd_resp_set_type(r,"application/json");
 httpd_resp_sendstr_chunk(r,"{\"jsonrpc\":\"2.0\",\"id\":");httpd_resp_sendstr_chunk(r,s);cJSON_free(s);
 char meta[384];snprintf(meta,sizeof(meta),",\"result\":{\"isError\":false,\"content\":[{\"type\":\"text\",\"text\":\"Fresh phone screenshot: %u bytes; USB acquisition %ld ms. Inspect the PNG visually; tap using original image pixel coordinates.\"},{\"type\":\"image\",\"mimeType\":\"image/png\",\"data\":\"",(unsigned)phone_result.size,phone_result.elapsed_ms);
 if(httpd_resp_sendstr_chunk(r,meta)!=ESP_OK)return ESP_FAIL;
 unsigned char buf[4097];
 for(size_t off=0;off<phone_result.size;){size_t n=phone_result.size-off;if(n>3072)n=3072;size_t enc=0;
  if(mbedtls_base64_encode(buf,sizeof(buf),&enc,phone_result.image+off,n))return ESP_FAIL;
  if(httpd_resp_send_chunk(r,(char*)buf,enc)!=ESP_OK)return ESP_FAIL;
  off+=n;
 }
 httpd_resp_sendstr_chunk(r,"\"}]}}");return httpd_resp_send_chunk(r,NULL,0);
}
static bool integer(cJSON *args,const char *name,int min,int max,int *v){cJSON *x=cJSON_GetObjectItemCaseSensitive(args,name);if(!cJSON_IsNumber(x)||!isfinite(x->valuedouble)||x->valuedouble<min||x->valuedouble>max||floor(x->valuedouble)!=x->valuedouble)return false;*v=x->valueint;return true;}
static const char tools[]="{\"tools\":["
"{\"name\":\"phone_wake_screen\",\"description\":\"Wake the screen without toggling power. Does not unlock the phone.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}},"
"{\"name\":\"phone_input_password\",\"description\":\"Input a known numeric lock-screen PIN (4-16 digits) into an already focused PIN field. Inspect the lock screen first. submit defaults to false; true also presses Enter. Never guess or automatically retry. Input success does not prove the phone unlocked. PIN is not persisted or echoed.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"password\":{\"type\":\"string\",\"pattern\":\"^[0-9]{4,16}$\",\"minLength\":4,\"maxLength\":16},\"submit\":{\"type\":\"boolean\",\"default\":false}},\"required\":[\"password\"],\"additionalProperties\":false}},"
"{\"name\":\"phone_status\",\"description\":\"Get S3 network and phone ADB connection status\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}},"
"{\"name\":\"phone_screenshot\",\"description\":\"Capture fresh full-resolution phone screenshot using S3 standalone ADB. Returns PNG image. Coordinates use original screenshot pixels.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}},"
"{\"name\":\"phone_tap\",\"description\":\"Tap original phone screenshot pixel coordinates\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"x\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":16383},\"y\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":16383}},\"required\":[\"x\",\"y\"],\"additionalProperties\":false}},"
"{\"name\":\"phone_swipe\",\"description\":\"Swipe using original screenshot pixels\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"x1\":{\"type\":\"integer\"},\"y1\":{\"type\":\"integer\"},\"x2\":{\"type\":\"integer\"},\"y2\":{\"type\":\"integer\"},\"duration_ms\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":10000}},\"required\":[\"x1\",\"y1\",\"x2\",\"y2\",\"duration_ms\"],\"additionalProperties\":false}},"
"{\"name\":\"phone_press_key\",\"description\":\"Press Android navigation key\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"key\":{\"type\":\"string\",\"enum\":[\"BACK\",\"HOME\",\"ENTER\",\"APP_SWITCH\"]}},\"required\":[\"key\"],\"additionalProperties\":false}}]}";
static esp_err_t mcp(httpd_req_t *r){
 if(!authorized(r))return ESP_OK;
 if(r->content_len<=0||r->content_len>8192){httpd_resp_set_status(r,"400 Bad Request");return httpd_resp_sendstr(r,"Invalid body size");}
 char *body=malloc(r->content_len+1);if(!body)return ESP_ERR_NO_MEM;int got=0;
 while(got<r->content_len){int n=httpd_req_recv(r,body+got,r->content_len-got);if(n<=0){free(body);return ESP_FAIL;}got+=n;}body[got]=0;
 cJSON *q=cJSON_Parse(body);mbedtls_platform_zeroize(body,r->content_len);free(body);
 cJSON *id=cJSON_GetObjectItemCaseSensitive(q,"id"),*method=cJSON_GetObjectItemCaseSensitive(q,"method");
 if(!q||!cJSON_IsObject(q)||!cJSON_IsString(method)){cJSON_Delete(q);httpd_resp_set_status(r,"400 Bad Request");return httpd_resp_sendstr(r,"Invalid JSON-RPC request");}
 if(!id){cJSON_Delete(q);httpd_resp_set_status(r,"202 Accepted");return httpd_resp_send(r,NULL,0);}
 cJSON *root=cJSON_CreateObject();cJSON_AddStringToObject(root,"jsonrpc","2.0");cJSON_AddItemToObject(root,"id",cJSON_Duplicate(id,true));
 const char *m=method->valuestring;bool image=false;
 if(!strcmp(m,"initialize")){
  cJSON *result=cJSON_AddObjectToObject(root,"result");cJSON_AddStringToObject(result,"protocolVersion","2025-06-18");cJSON_AddStringToObject(result,"instructions","Prefer phone_list_apps and phone_launch_app for opening apps by package, and phone_foreground_app to verify. Use phone_ui_hierarchy for available control bounds. Use phone_adb_shell for additional authorized Android shell operations; it runs on the phone, not the computer. Respect shell exit codes and truncation. Do not clear data, uninstall, change security settings, reboot or perform external actions unless authorized by the user. Use phone_screenshot to inspect the phone visually. Locate targets in the original image pixel coordinates, then use phone_tap, phone_swipe or phone_press_key. For a known PIN use phone_wake_screen, inspect and reveal the PIN field, then phone_input_password once. Never infer unlock success from command delivery alone. Capture a fresh screenshot after an action to verify it. Image interpretation is performed by the calling AI; no OCR service is required.");cJSON *caps=cJSON_AddObjectToObject(result,"capabilities");cJSON_AddObjectToObject(caps,"tools");cJSON *info=cJSON_AddObjectToObject(result,"serverInfo");cJSON_AddStringToObject(info,"name","esp32-s3-phone");cJSON_AddStringToObject(info,"version","0.4.0");
 }else if(!strcmp(m,"ping"))cJSON_AddObjectToObject(root,"result");
 else if(!strcmp(m,"tools/list")){
  cJSON *result=cJSON_Parse(tools),*extra=cJSON_Parse(command_tools_json()),*item;
  while((item=cJSON_DetachItemFromArray(extra,0)))cJSON_AddItemToArray(cJSON_GetObjectItemCaseSensitive(result,"tools"),item);
  cJSON_Delete(extra);cJSON_AddItemToObject(root,"result",result);
 }
 else if(!strcmp(m,"tools/call")){
  cJSON *params=cJSON_GetObjectItemCaseSensitive(q,"params"),*name=cJSON_GetObjectItemCaseSensitive(params,"name"),*args=cJSON_GetObjectItemCaseSensitive(params,"arguments");
  char cmd[PHONE_COMMAND_CAPACITY]={0};bool valid=true;bool sensitive=false;bool shell_result=false;char validation_error[160]={0};
  if(!cJSON_IsString(name)){text_result(root,"Missing tool name",true);}
  else if(!strcmp(name->valuestring,"phone_status")){cJSON *st=status_json();char *s=cJSON_PrintUnformatted(st);text_result(root,s,false);cJSON_free(s);cJSON_Delete(st);}
  else{
   if(!strcmp(name->valuestring,"phone_screenshot")){strcpy(cmd,"exec:screencap -p");image=true;}
   else if(!strcmp(name->valuestring,"phone_wake_screen")){strcpy(cmd,"shell:input keyevent 224 && echo ACTION_OK");}
   else if(!strcmp(name->valuestring,"phone_input_password")){
    sensitive=true;cJSON *password=cJSON_GetObjectItemCaseSensitive(args,"password"),*submit=cJSON_GetObjectItemCaseSensitive(args,"submit");
    valid=cJSON_IsString(password)&&(!submit||cJSON_IsBool(submit));
    if(valid){size_t n=strlen(password->valuestring);valid=n>=4&&n<=16;for(size_t i=0;i<n;i++)if(password->valuestring[i]<'0'||password->valuestring[i]>'9')valid=false;}
    if(valid)snprintf(cmd,sizeof(cmd),"shell:input text '%s'%s && echo ACTION_OK",password->valuestring,cJSON_IsTrue(submit)?" && input keyevent 66":"");
    if(cJSON_IsString(password))mbedtls_platform_zeroize(password->valuestring,strlen(password->valuestring));
   }
   else if(!strcmp(name->valuestring,"phone_tap")){int x,y;valid=integer(args,"x",0,16383,&x)&&integer(args,"y",0,16383,&y);if(valid)snprintf(cmd,sizeof(cmd),"shell:input tap %d %d && echo ACTION_OK",x,y);}
   else if(!strcmp(name->valuestring,"phone_swipe")){int a,b,c,d,t;valid=integer(args,"x1",0,16383,&a)&&integer(args,"y1",0,16383,&b)&&integer(args,"x2",0,16383,&c)&&integer(args,"y2",0,16383,&d)&&integer(args,"duration_ms",1,10000,&t);if(valid)snprintf(cmd,sizeof(cmd),"shell:input swipe %d %d %d %d %d && echo ACTION_OK",a,b,c,d,t);}
   else if(!strcmp(name->valuestring,"phone_press_key")){cJSON *k=cJSON_GetObjectItemCaseSensitive(args,"key");int code=0;if(cJSON_IsString(k)){if(!strcmp(k->valuestring,"BACK"))code=4;else if(!strcmp(k->valuestring,"HOME"))code=3;else if(!strcmp(k->valuestring,"ENTER"))code=66;else if(!strcmp(k->valuestring,"APP_SWITCH"))code=187;}valid=code!=0;if(valid)snprintf(cmd,sizeof(cmd),"shell:input keyevent %d && echo ACTION_OK",code);}
   else {shell_result=true;valid=build_command_tool(name->valuestring,args,cmd,sizeof(cmd),validation_error,sizeof(validation_error));}
   if(!valid)text_result(root,validation_error[0]?validation_error:"Unknown tool or invalid arguments",true);
   else if(!phone_execute(cmd,image))text_result(root,"ADB busy or timed out; restart board if timeout persists",true);
   else if(!phone_result.ok)text_result(root,phone_result.error,true);
   else if(image){esp_err_t e=image_result(r,id);cJSON_Delete(root);cJSON_Delete(q);return e;}
   else if(shell_result)command_result(root);
   else if(sensitive){bool sent=strstr(phone_result.text,"ACTION_OK")!=NULL;text_result(root,sent?"PIN input delivered. Verify the lock screen to determine whether unlocking succeeded.":"PIN input failed; no automatic retry was performed.",!sent);}
   else text_result(root,phone_result.text,!strstr(phone_result.text,"ACTION_OK"));
   mbedtls_platform_zeroize(cmd,sizeof(cmd));
  }
 }else{cJSON *e=cJSON_AddObjectToObject(root,"error");cJSON_AddNumberToObject(e,"code",-32601);cJSON_AddStringToObject(e,"message","Method not found");}
 esp_err_t result=json_send(r,root);cJSON_Delete(root);cJSON_Delete(q);return result;
}
static void wifi_event(void *arg,esp_event_base_t base,int32_t event,void *data){
 if(base==WIFI_EVENT&&event==WIFI_EVENT_STA_START)esp_wifi_connect();
 else if(base==WIFI_EVENT&&event==WIFI_EVENT_STA_DISCONNECTED){puts("WIFI_DISCONNECTED retrying");esp_wifi_connect();}
 else if(base==IP_EVENT&&event==IP_EVENT_STA_GOT_IP){ip_event_got_ip_t *e=data;snprintf(ip,sizeof(ip),IPSTR,IP2STR(&e->ip_info.ip));printf("MCP_URL=http://%s/mcp\n",ip);}
}
void network_start(void){
 esp_err_t e=nvs_flash_init();if(e==ESP_ERR_NVS_NO_FREE_PAGES||e==ESP_ERR_NVS_NEW_VERSION_FOUND){ESP_ERROR_CHECK(nvs_flash_erase());e=nvs_flash_init();}ESP_ERROR_CHECK(e);
 ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());esp_netif_create_default_wifi_sta();
 wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&init));
 ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event,NULL));ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_event,NULL));
 wifi_config_t config={0};snprintf((char*)config.sta.ssid,sizeof(config.sta.ssid),"%s",PHONE_WIFI_SSID);snprintf((char*)config.sta.password,sizeof(config.sta.password),"%s",PHONE_WIFI_PASSWORD);
 ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&config));ESP_ERROR_CHECK(esp_wifi_start());ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));ESP_ERROR_CHECK(esp_wifi_set_max_tx_power(40));
 httpd_config_t hc=HTTPD_DEFAULT_CONFIG();hc.stack_size=24576;hc.recv_wait_timeout=15;hc.send_wait_timeout=30;hc.lru_purge_enable=true;httpd_handle_t server=NULL;ESP_ERROR_CHECK(httpd_start(&server,&hc));
 httpd_uri_t a={.uri="/mcp",.method=HTTP_POST,.handler=mcp},b={.uri="/mcp",.method=HTTP_GET,.handler=get_mcp},c={.uri="/health",.method=HTTP_GET,.handler=health};
 ESP_ERROR_CHECK(httpd_register_uri_handler(server,&a));ESP_ERROR_CHECK(httpd_register_uri_handler(server,&b));ESP_ERROR_CHECK(httpd_register_uri_handler(server,&c));
}
