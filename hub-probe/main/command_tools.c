#include "command_tools.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "mbedtls/platform_util.h"
static const char *string_arg(cJSON *args,const char *name){cJSON *v=cJSON_GetObjectItemCaseSensitive(args,name);return cJSON_IsString(v)?v->valuestring:NULL;}
static bool number(cJSON *args,const char *name,int fallback,int min,int max,int *out){cJSON *v=cJSON_GetObjectItemCaseSensitive(args,name);if(!v){*out=fallback;return true;}if(!cJSON_IsNumber(v)||!isfinite(v->valuedouble)||floor(v->valuedouble)!=v->valuedouble||v->valuedouble<min||v->valuedouble>max)return false;*out=v->valueint;return true;}
static bool identifier(const char *s,bool component){if(!s||!*s||strlen(s)>200)return false;for(const unsigned char *p=(const unsigned char*)s;*p;p++){if((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='.'||*p=='_'||(component&&(*p=='/'||*p=='$')))continue;return false;}return (component||s[0]!='.')&&s[0]!='_'&&s[0]!='/';}
static bool quote(const char *s,char *dst,size_t cap){size_t n=0;if(cap<3)return false;dst[n++]='\'';for(;*s;s++){const char *v=*s=='\''?"'\\''":NULL;if(v){if(n+4+2>cap)return false;memcpy(dst+n,v,4);n+=4;}else{if(n+3>cap)return false;dst[n++]=*s;}}dst[n++]='\'';dst[n]=0;return true;}
static bool wrap(const char *raw,int seconds,char *dst,size_t cap){char quoted[3200];if(!quote(raw,quoted,sizeof(quoted)))return false;int n=snprintf(dst,cap,"shell:timeout %ds sh -c %s 2>&1; r=$?; printf '\\n__S3_EXIT__%%d\\n' \"$r\"",seconds,quoted);mbedtls_platform_zeroize(quoted,sizeof(quoted));return n>0&&(size_t)n<cap;}
bool build_command_tool(const char *name,cJSON *args,char *dst,size_t cap,char *error,size_t ecap){
 char raw[2000]={0};int timeout=15;bool valid=true;const char *why="Invalid arguments";
 if(!strcmp(name,"phone_adb_shell")){
  const char *command=string_arg(args,"command");valid=command&&*command&&strlen(command)<=768&&number(args,"timeout_seconds",15,1,30,&timeout);if(valid){snprintf(raw,sizeof(raw),"%s",command);}why="command must contain 1-768 UTF-8 bytes; timeout_seconds must be 1-30";
 }else if(!strcmp(name,"phone_list_apps")){
  const char *filter=string_arg(args,"filter"),*kind=string_arg(args,"kind");cJSON *f=cJSON_GetObjectItemCaseSensitive(args,"filter"),*k=cJSON_GetObjectItemCaseSensitive(args,"kind");
  valid=(!f||cJSON_IsString(f))&&(!k||cJSON_IsString(k))&&(!filter||!*filter||identifier(filter,false));const char *flag="";
  if(kind){if(!strcmp(kind,"third_party"))flag="-3";else if(!strcmp(kind,"system"))flag="-s";else if(strcmp(kind,"all"))valid=false;}
  if(valid){snprintf(raw,sizeof(raw),"pm list packages %s %s",flag,filter?filter:"");}why="kind must be all, third_party or system; filter must be a package-name substring";
 }else if(!strcmp(name,"phone_launch_app")){
  const char *p=string_arg(args,"package"),*component=string_arg(args,"activity");cJSON *v=cJSON_GetObjectItemCaseSensitive(args,"activity");valid=identifier(p,false)&&(!v||cJSON_IsString(v))&&(!component||identifier(component,true));
  if(valid){
   char launch[1200];
   if(component){
    if(strchr(component,'/'))snprintf(launch,sizeof(launch),"a='%s'; ",component);
    else snprintf(launch,sizeof(launch),"a='%s/%s'; ",p,component);
   }else snprintf(launch,sizeof(launch),"a=$(cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p '%s' | tail -n 1); ",p);
   snprintf(raw,sizeof(raw),"%scase \"$a\" in */*) ;; *) echo 'No launcher activity resolved'; exit 1;; esac; o=$(am start -W -n \"$a\" 2>&1); r=$?; printf '%%s\\n' \"$o\"; case \"$o\" in *Error:*|*Exception:*) exit 1;; esac; exit \"$r\"",launch);
  }
  why="A valid package name is required; activity must be a valid optional activity/component";
 }else if(!strcmp(name,"phone_stop_app")){
  const char *p=string_arg(args,"package");valid=identifier(p,false);if(valid){snprintf(raw,sizeof(raw),"am force-stop '%s'",p);}why="A valid package name is required";
 }else if(!strcmp(name,"phone_app_info")){
  const char *p=string_arg(args,"package");valid=identifier(p,false);if(valid){snprintf(raw,sizeof(raw),"pm path '%s' && dumpsys package '%s' | grep -E 'versionName=|versionCode=|firstInstallTime|lastUpdateTime|userId=|codePath='",p,p);}why="A valid package name is required";
 }else if(!strcmp(name,"phone_foreground_app")){
  strcpy(raw,"dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'; dumpsys window | grep -E 'mCurrentFocus|mFocusedApp|mTopFocusedDisplayId'");
 }else if(!strcmp(name,"phone_device_info")){
  strcpy(raw,"echo MODEL; getprop ro.product.model; echo ANDROID; getprop ro.build.version.release; echo SDK; getprop ro.build.version.sdk; echo DISPLAY; wm size; wm density; echo BATTERY; dumpsys battery");
 }else if(!strcmp(name,"phone_ui_hierarchy")){
  timeout=25;strcpy(raw,"uiautomator dump /data/local/tmp/s3-mcp-ui.xml >/dev/null && cat /data/local/tmp/s3-mcp-ui.xml; r=$?; rm -f /data/local/tmp/s3-mcp-ui.xml; exit \"$r\"");
 }else if(!strcmp(name,"phone_open_url")){
  const char *url=string_arg(args,"url");char quoted[1600];valid=url&&*url&&strlen(url)<=384&&strchr(url,':')&&quote(url,quoted,sizeof(quoted));if(valid){snprintf(raw,sizeof(raw),"am start -W -a android.intent.action.VIEW -d %s",quoted);}why="url must contain a scheme and be at most 384 UTF-8 bytes";
 }else if(!strcmp(name,"phone_input_text")){
  const char *text=string_arg(args,"text");char transformed[768],quoted[1100];size_t n=0;valid=text&&*text&&strlen(text)<=256&&!strstr(text,"%s");
  if(valid){for(const unsigned char *p=(const unsigned char*)text;*p;p++){if(*p<32||*p>126){valid=false;break;}if(*p==' '){transformed[n++]='%';transformed[n++]='s';}else transformed[n++]=*p;}transformed[n]=0;}
  if(valid){valid=quote(transformed,quoted,sizeof(quoted));}
  if(valid){snprintf(raw,sizeof(raw),"input text %s",quoted);}
  mbedtls_platform_zeroize(transformed,sizeof(transformed));mbedtls_platform_zeroize(quoted,sizeof(quoted));why="text must contain 1-256 printable ASCII characters; literal %s and Unicode input are not supported by Android input text";
 }else if(!strcmp(name,"phone_keyevent")){
  int code;cJSON *longpress=cJSON_GetObjectItemCaseSensitive(args,"longpress");valid=cJSON_HasObjectItem(args,"code")&&number(args,"code",0,0,1000,&code)&&(!longpress||cJSON_IsBool(longpress));if(valid){snprintf(raw,sizeof(raw),"input keyevent %s %d",cJSON_IsTrue(longpress)?"--longpress":"",code);}why="code must be an integer 0-1000; longpress must be boolean";
 }else if(!strcmp(name,"phone_long_press")){
  int x,y,ms;valid=cJSON_HasObjectItem(args,"x")&&cJSON_HasObjectItem(args,"y")&&number(args,"x",0,0,16383,&x)&&number(args,"y",0,0,16383,&y)&&number(args,"duration_ms",800,100,10000,&ms);if(valid){snprintf(raw,sizeof(raw),"input swipe %d %d %d %d %d",x,y,x,y,ms);}why="x/y must be original pixel coordinates; duration_ms must be 100-10000";
 }else{snprintf(error,ecap,"Unknown tool");return false;}
 if(valid){valid=wrap(raw,timeout,dst,cap);}
 if(!valid){snprintf(error,ecap,"%s",why);}
 mbedtls_platform_zeroize(raw,sizeof(raw));return valid;
}

const char *command_tools_json(void){return
"[{\"name\":\"phone_adb_shell\",\"description\":\"Execute an Android shell command directly on the phone through S3. Supports pipes and shell syntax; not a host-computer adb command. Same permissions as authorized ADB shell, no automatic root. Text output up to 32 KiB; returns exit code, elapsed time and truncation. Use bounded commands; do not run interactive or binary-output commands.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"command\":{\"type\":\"string\",\"minLength\":1,\"maxLength\":768},\"timeout_seconds\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":30,\"default\":15}},\"required\":[\"command\"],\"additionalProperties\":false}},{\"name\":\"phone_list_apps\",\"description\":\"List installed package IDs. Filter is a package substring, not a localized app label. Use this before command-based launch.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"filter\":{\"type\":\"string\",\"maxLength\":200},\"kind\":{\"type\":\"string\",\"enum\":[\"all\",\"third_party\",\"system\"],\"default\":\"all\"}},\"required\":[],\"additionalProperties\":false}},{\"name\":\"phone_launch_app\",\"description\":\"Launch an app by package ID, optionally a specific Activity/component. Prefer this over searching launcher screenshots. A successful command may still show a lock screen; verify foreground activity or screenshot.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"package\":{\"type\":\"string\",\"pattern\":\"^[A-Za-z0-9][A-Za-z0-9_.]*$\",\"maxLength\":200},\"activity\":{\"type\":\"string\",\"maxLength\":200}},\"required\":[\"package\"],\"additionalProperties\":false}},{\"name\":\"phone_stop_app\",\"description\":\"Force-stop one app process by package ID. Does not clear app data.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"package\":{\"type\":\"string\",\"pattern\":\"^[A-Za-z0-9][A-Za-z0-9_.]*$\",\"maxLength\":200}},\"required\":[\"package\"],\"additionalProperties\":false}},{\"name\":\"phone_app_info\",\"description\":\"Read APK path, version and install metadata for one package.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"package\":{\"type\":\"string\",\"pattern\":\"^[A-Za-z0-9][A-Za-z0-9_.]*$\",\"maxLength\":200}},\"required\":[\"package\"],\"additionalProperties\":false}},{\"name\":\"phone_foreground_app\",\"description\":\"Read resumed activity/package via dumpsys; use it to verify command-based app launch.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"required\":[],\"additionalProperties\":false}},{\"name\":\"phone_device_info\",\"description\":\"Read phone model, Android version, display dimensions/density and battery state.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"required\":[],\"additionalProperties\":false}},{\"name\":\"phone_ui_hierarchy\",\"description\":\"Read visible Android UI hierarchy XML with text, resource IDs and bounds; may be incomplete on custom-rendered apps. Temporary file is removed. May take up to 25 seconds; screenshot is the fallback.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"required\":[],\"additionalProperties\":false}},{\"name\":\"phone_open_url\",\"description\":\"Open a URL/deep link through Android ACTION_VIEW. May display an app chooser.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"url\":{\"type\":\"string\",\"minLength\":1,\"maxLength\":384}},\"required\":[\"url\"],\"additionalProperties\":false}},{\"name\":\"phone_input_text\",\"description\":\"Type printable ASCII into the focused field, without submitting it. Spaces supported; Unicode and literal %s unsupported. Use phone_input_password for PIN entry.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"text\":{\"type\":\"string\",\"minLength\":1,\"maxLength\":256}},\"required\":[\"text\"],\"additionalProperties\":false}},{\"name\":\"phone_keyevent\",\"description\":\"Send numeric Android keycode; examples: 3 HOME, 4 BACK, 66 ENTER, 67 DELETE, 223 SLEEP, 224 WAKEUP.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"code\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":1000},\"longpress\":{\"type\":\"boolean\",\"default\":false}},\"required\":[\"code\"],\"additionalProperties\":false}},{\"name\":\"phone_long_press\",\"description\":\"Long-press at original screenshot pixel coordinates.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{\"x\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":16383},\"y\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":16383},\"duration_ms\":{\"type\":\"integer\",\"minimum\":100,\"maximum\":10000,\"default\":800}},\"required\":[\"x\",\"y\"],\"additionalProperties\":false}}]";}
