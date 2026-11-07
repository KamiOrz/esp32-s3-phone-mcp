#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "usb/usb_host.h"
#include "esp_intr_alloc.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "mbedtls/pk.h"
#include "mbedtls/platform_util.h"
#include "mbedtls/base64.h"
#include "psa/crypto.h"
#include "adb_key.h"
#include "phone.h"
#include "esp_heap_caps.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#define A_CNXN 0x4e584e43u
#define A_AUTH 0x48545541u
#define A_OPEN 0x4e45504fu
#define A_OKAY 0x59414b4fu
#define A_WRTE 0x45545257u
#define A_CLSE 0x45534c43u
static usb_host_client_handle_t client;
static usb_device_handle_t adbdev;
static usb_transfer_t *rx,*tx;
static uint8_t epin,epout;
static mbedtls_pk_context key;
static uint32_t hdr[6],out_hdr[6];
static uint8_t payload[4096],out_data[4096];
static int received,wanted,send_len,send_stage,auth_count;
static bool connected,txbusy,operation_active,image_mode;
static uint32_t stream_id;
static int64_t restart_at;
static bool network_started,keepalive;
static int64_t last_activity;
static int64_t op_started;
static QueueHandle_t requests;
static SemaphoreHandle_t completed,request_lock;
typedef struct {char command[PHONE_COMMAND_CAPACITY];bool image;} request_t;
phone_result_t phone_result;
static unsigned char *image_buffer;
static bool pending_packet;
static uint32_t pending_cmd,pending_a,pending_b;
static int pending_len;
static unsigned char pending_data[4096];
#define IMAGE_CAPACITY (6*1024*1024)
bool phone_execute(const char *command,bool screenshot){
 if(!requests||xSemaphoreTake(request_lock,0)!=pdTRUE)return false;
 while(xSemaphoreTake(completed,0)==pdTRUE){}
 static request_t q;memset(&q,0,sizeof(q));snprintf(q.command,sizeof(q.command),"%s",command);q.image=screenshot;
 if(xQueueSend(requests,&q,0)!=pdTRUE){mbedtls_platform_zeroize(&q,sizeof(q));xSemaphoreGive(request_lock);return false;}
 mbedtls_platform_zeroize(&q,sizeof(q));
 bool done=xSemaphoreTake(completed,pdMS_TO_TICKS(45000))==pdTRUE;
 if(done){xSemaphoreGive(request_lock);}else{restart_at=esp_timer_get_time()+2000000;}
 return done;
}
static void finish_operation(bool ok,const char *error){
 if(keepalive){operation_active=false;last_activity=esp_timer_get_time();keepalive=false;return;}
 phone_result.ok=ok;phone_result.connected=connected;
 if(error)snprintf(phone_result.error,sizeof(phone_result.error),"%s",error);
 phone_result.elapsed_ms=(esp_timer_get_time()-op_started)/1000;
 operation_active=false;last_activity=esp_timer_get_time();if(!keepalive)xSemaphoreGive(completed);keepalive=false;
}

static void packet(uint32_t cmd,uint32_t a,uint32_t b,const void *data,int len){
 if(len>4096){puts("ADB_ERROR send oversize");return;}
 if(txbusy){
  if(pending_packet){puts("ADB_ERROR pending queue full");restart_at=esp_timer_get_time()+2000000;return;}
  pending_cmd=cmd;pending_a=a;pending_b=b;pending_len=len;if(len)memcpy(pending_data,data,len);pending_packet=true;return;
 }
 uint32_t sum=0;for(int i=0;i<len;i++)sum+=((const uint8_t*)data)[i];
 out_hdr[0]=cmd;out_hdr[1]=a;out_hdr[2]=b;out_hdr[3]=len;out_hdr[4]=sum;out_hdr[5]=cmd^0xffffffffu;
 if(len){memcpy(out_data,data,len);}
 send_len=len;send_stage=0;txbusy=true;
 memcpy(tx->data_buffer,out_hdr,24);tx->num_bytes=24;

 esp_err_t e=usb_host_transfer_submit(tx);if(e!=ESP_OK){txbusy=false;printf("ADB_ERROR tx=%s\n",esp_err_to_name(e));}
}
static void handle_packet(void){
 uint32_t cmd=hdr[0],len=hdr[3];

 if(cmd==A_AUTH&&hdr[1]==1&&len==20){
  if(auth_count++==0){
   unsigned char sig[256];size_t n=0;
   int e=mbedtls_pk_sign(&key,MBEDTLS_MD_SHA1,payload,20,sig,sizeof(sig),&n);
   printf("S3_RSA_SIGN result=%d bytes=%u\n",e,(unsigned)n);
   if(e==0)packet(A_AUTH,2,0,sig,n);
  }else{
   puts("PHONE_AUTHORIZATION_REQUIRED: accept USB debugging on phone");
   packet(A_AUTH,3,0,adb_public_key,sizeof(adb_public_key));
  }
 }else if(cmd==A_CNXN){
  connected=true;printf("ADB_AUTHENTICATED banner=%.*s\n",(int)len,payload);phone_result.connected=true;
 }else if(cmd==A_WRTE&&operation_active&&hdr[2]==stream_id){
  if(keepalive){ /* Drain the keepalive stream without modifying the RPC result. */ }
  else if(image_mode){
   if(phone_result.size+len<=IMAGE_CAPACITY){memcpy(image_buffer+phone_result.size,payload,len);phone_result.size+=len;}
   else snprintf(phone_result.error,sizeof(phone_result.error),"Screenshot exceeds 6 MiB");
  }else{
   phone_result.total_received+=len;
   if(len>=sizeof(phone_result.tail)-1){memcpy(phone_result.tail,payload+len-(sizeof(phone_result.tail)-1),sizeof(phone_result.tail)-1);phone_result.tail_size=sizeof(phone_result.tail)-1;}
   else{size_t keep=phone_result.tail_size;if(keep+len>sizeof(phone_result.tail)-1)keep=sizeof(phone_result.tail)-1-len;memmove(phone_result.tail,phone_result.tail+phone_result.tail_size-keep,keep);memcpy(phone_result.tail+keep,payload,len);phone_result.tail_size=keep+len;}
   phone_result.tail[phone_result.tail_size]=0;
   size_t n=len;if(n>sizeof(phone_result.text)-1-phone_result.size){n=sizeof(phone_result.text)-1-phone_result.size;phone_result.truncated=true;}
   memcpy(phone_result.text+phone_result.size,payload,n);phone_result.size+=n;phone_result.text[phone_result.size]=0;
  }
  packet(A_OKAY,hdr[2],hdr[1],NULL,0);
 }else if(cmd==A_CLSE&&operation_active&&hdr[2]==stream_id){
  packet(A_CLSE,hdr[2],hdr[1],NULL,0);
  if(!keepalive&&image_mode&&(phone_result.size<8||memcmp(image_buffer,"\x89PNG\r\n\x1a\n",8)))snprintf(phone_result.error,sizeof(phone_result.error),"Phone did not return a PNG");
  bool ok=!phone_result.error[0];finish_operation(ok,NULL);

 }
}
static void rx_done(usb_transfer_t *t){
 if(t->status!=USB_TRANSFER_STATUS_COMPLETED){printf("ADB_ERROR rx_status=%d\n",t->status);restart_at=esp_timer_get_time()+2000000;return;}
 int n=t->actual_num_bytes;
 if(!wanted){
  if(n!=24){printf("ADB_ERROR header_size=%d\n",n);return;}
  memcpy(hdr,t->data_buffer,24);
  if(hdr[5]!=(hdr[0]^0xffffffffu)||hdr[3]>sizeof(payload)){puts("ADB_ERROR invalid_header");return;}
  wanted=hdr[3];received=0;
  if(!wanted)handle_packet();
 }else{
  if(n<=0||n>wanted-received){puts("ADB_ERROR payload_size");return;}
  memcpy(payload+received,t->data_buffer,n);received+=n;
  if(received==wanted){wanted=0;handle_packet();}
 }
 t->num_bytes=wanted?((wanted-received+63)/64)*64:64;
 esp_err_t e=usb_host_transfer_submit(t);if(e!=ESP_OK)printf("ADB_ERROR rx_submit=%s\n",esp_err_to_name(e));
}
static void tx_done(usb_transfer_t *t){
 if(t->status!=USB_TRANSFER_STATUS_COMPLETED){txbusy=false;printf("ADB_ERROR tx_status=%d\n",t->status);return;}
 if(send_stage==0&&send_len){send_stage=1;memcpy(t->data_buffer,out_data,send_len);t->num_bytes=send_len;esp_err_t e=usb_host_transfer_submit(t);if(e!=ESP_OK){txbusy=false;printf("ADB_ERROR tx_payload=%s\n",esp_err_to_name(e));}}
 else {mbedtls_platform_zeroize(t->data_buffer,t->num_bytes);mbedtls_platform_zeroize(out_data,sizeof(out_data));txbusy=false;}
}
static void start_adb(usb_device_handle_t dev,int iface,int alt){
 esp_err_t e=usb_host_interface_claim(client,dev,iface,alt);printf("ADB_CLAIM=%s IN=%02x OUT=%02x\n",esp_err_to_name(e),epin,epout);if(e!=ESP_OK)return;
 adbdev=dev;
 ESP_ERROR_CHECK(usb_host_transfer_alloc(4096,0,&rx));ESP_ERROR_CHECK(usb_host_transfer_alloc(4096,0,&tx));
 rx->device_handle=dev;rx->bEndpointAddress=epin;rx->callback=rx_done;rx->num_bytes=64;
 tx->device_handle=dev;tx->bEndpointAddress=epout;tx->callback=tx_done;
 ESP_ERROR_CHECK(usb_host_transfer_submit(rx));
 const char banner[]="host::features=;";
 packet(A_CNXN,0x01000000,4096,banner,sizeof(banner));
}
static void event(const usb_host_client_event_msg_t *msg,void *arg){
 if(msg->event==USB_HOST_CLIENT_EVENT_NEW_DEV){
  usb_device_handle_t dev;esp_err_t e=usb_host_device_open(client,msg->new_dev.address,&dev);if(e!=ESP_OK)return;
  const usb_device_desc_t *d;ESP_ERROR_CHECK(usb_host_get_device_descriptor(dev,&d));printf("USB_DEVICE address=%u VID=%04x PID=%04x\n",msg->new_dev.address,d->idVendor,d->idProduct);
  const usb_config_desc_t *cfg;ESP_ERROR_CHECK(usb_host_get_active_config_descriptor(dev,&cfg));
  const uint8_t *p=(const uint8_t*)cfg;int iface=-1,alt=0;bool isadb=false;uint8_t in=0,out=0;
  for(int off=0;off+2<=cfg->wTotalLength;){int n=p[off];if(n<2||off+n>cfg->wTotalLength)break;
   if(p[off+1]==4&&n>=9){isadb=p[off+5]==255&&p[off+6]==66&&p[off+7]==1;if(isadb){iface=p[off+2];alt=p[off+3];puts("ADB_INTERFACE_FOUND");}}
   if(p[off+1]==5&&n>=7&&isadb&&(p[off+3]&3)==2){if(p[off+2]&128)in=p[off+2];else out=p[off+2];}
   off+=n;
  }
  if(iface>=0&&in&&out&&!adbdev){epin=in;epout=out;start_adb(dev,iface,alt);}else usb_host_device_close(client,dev);
 }else if(msg->event==USB_HOST_CLIENT_EVENT_DEV_GONE){if(msg->dev_gone.dev_hdl==adbdev){connected=false;phone_result.connected=false;restart_at=esp_timer_get_time()+2000000;if(operation_active)finish_operation(false,"Phone disconnected; restart board to reconnect");}puts("USB_DEVICE_GONE");}
}
static void daemon(void *arg){while(1){uint32_t f;usb_host_lib_handle_events(portMAX_DELAY,&f);}}
void app_main(void){
 esp_log_level_set("*",ESP_LOG_WARN);

 puts("PHONE_WIFI_MCP v6: standalone USB ADB + Wi-Fi MCP");
 image_buffer=heap_caps_malloc(IMAGE_CAPACITY,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
 if(!image_buffer){puts("ERROR PSRAM image allocation failed");return;}
 phone_result.image=image_buffer;
 requests=xQueueCreate(1,sizeof(request_t));completed=xSemaphoreCreateBinary();request_lock=xSemaphoreCreateMutex();

 ESP_ERROR_CHECK(psa_crypto_init());mbedtls_pk_init(&key);
 int r=mbedtls_pk_parse_key(&key,(const unsigned char*)adb_private_key,sizeof(adb_private_key),NULL,0);printf("S3_PRIVATE_KEY_PARSE=%d\n",r);if(r)return;
 usb_host_config_t c={0};c.intr_flags=ESP_INTR_FLAG_LEVEL1;ESP_ERROR_CHECK(usb_host_install(&c));
 xTaskCreate(daemon,"usb_daemon",6144,NULL,20,NULL);
 usb_host_client_config_t cc={0};cc.max_num_event_msg=10;cc.async.client_event_callback=event;ESP_ERROR_CHECK(usb_host_client_register(&cc,&client));
 int64_t last=0;
 while(1){
  usb_host_client_handle_events(client,pdMS_TO_TICKS(10));
  if(pending_packet&&!txbusy){pending_packet=false;packet(pending_cmd,pending_a,pending_b,pending_data,pending_len);mbedtls_platform_zeroize(pending_data,sizeof(pending_data));}
  if(!operation_active&&!txbusy&&!pending_packet){static request_t q;
   if(xQueueReceive(requests,&q,0)==pdTRUE){
    keepalive=false;memset(&phone_result,0,sizeof(phone_result));phone_result.image=image_buffer;phone_result.connected=connected;op_started=esp_timer_get_time();
    if(!connected)finish_operation(false,"Phone ADB is not connected");
    else{operation_active=true;image_mode=q.image;stream_id++;packet(A_OPEN,stream_id,0,q.command,strlen(q.command)+1);}
    mbedtls_platform_zeroize(&q,sizeof(q));
   }
  }
  int64_t now=esp_timer_get_time();
  if(connected&&!operation_active&&!txbusy&&!pending_packet&&now-last_activity>1000000){
   operation_active=true;keepalive=true;image_mode=false;op_started=now;
   stream_id++;const char cmd[]="exec:echo S3_KEEPALIVE";packet(A_OPEN,stream_id,0,cmd,sizeof(cmd));
  }
if(!network_started&&now>8000000){network_started=true;network_start();}
  if(restart_at&&now>restart_at){puts("USB_RECOVERY_RESTART");esp_restart();}
  if(now-last>5000000){last=now;usb_host_lib_info_t i={0};usb_host_lib_info(&i);printf("STATUS devices=%d authenticated=%d heap=%lu\n",i.num_devices,connected,(unsigned long)esp_get_free_heap_size());}
 }
}
