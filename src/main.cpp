#include <Arduino.h>
#include "usb/usb_host.h"
#include "esp_intr_alloc.h"
static usb_host_client_handle_t client;
static usb_device_handle_t device;
static void event(const usb_host_client_event_msg_t *msg, void *) {
 if(msg->event==USB_HOST_CLIENT_EVENT_NEW_DEV){
  Serial.printf("NEW_DEVICE address=%u\n",msg->new_dev.address);
  esp_err_t e=usb_host_device_open(client,msg->new_dev.address,&device);
  Serial.printf("OPEN=%s\n",esp_err_to_name(e)); if(e!=ESP_OK)return;
  const usb_device_desc_t *d; usb_host_get_device_descriptor(device,&d);
  Serial.printf("VID=%04x PID=%04x USB=%04x\n",d->idVendor,d->idProduct,d->bcdUSB);
  const usb_config_desc_t *cfg; e=usb_host_get_active_config_descriptor(device,&cfg);
  if(e!=ESP_OK)return;
  const uint8_t *p=(const uint8_t*)cfg;int off=0;
  while(off+2<=cfg->wTotalLength){
   int len=p[off]; if(len<2||off+len>cfg->wTotalLength)break;
   if(p[off+1]==4 && len>=9){
    Serial.printf("INTERFACE=%u ALT=%u CLASS=%02x SUB=%02x PROTO=%02x\n",p[off+2],p[off+3],p[off+5],p[off+6],p[off+7]);
    if(p[off+5]==255&&p[off+6]==66&&p[off+7]==1)Serial.println("ADB_INTERFACE_FOUND");
   }
   if(p[off+1]==5 && len>=7)Serial.printf("ENDPOINT=%02x ATTR=%02x MPS=%u\n",p[off+2],p[off+3],p[off+4]|(p[off+5]<<8));
   off+=len;
  }
 }else{Serial.println("DEVICE_GONE");usb_host_device_close(client,msg->dev_gone.dev_hdl);device=nullptr;}
}
static void daemon(void*){while(true){uint32_t f;usb_host_lib_handle_events(portMAX_DELAY,&f);}}
void setup(){
 Serial.begin(115200);delay(1000);Serial.println("PHONE_USB_PROBE v1");
 usb_host_config_t c={};c.intr_flags=ESP_INTR_FLAG_LEVEL1;
 esp_err_t e=usb_host_install(&c);Serial.printf("HOST_INSTALL=%s\n",esp_err_to_name(e));if(e!=ESP_OK)return;
 xTaskCreate(daemon,"usb_daemon",4096,nullptr,20,nullptr);
 usb_host_client_config_t cc={};cc.max_num_event_msg=5;cc.async.client_event_callback=event;
 e=usb_host_client_register(&cc,&client);Serial.printf("CLIENT_REGISTER=%s\n",esp_err_to_name(e));
}
void loop(){
 if(client)usb_host_client_handle_events(client,pdMS_TO_TICKS(100));else delay(100);
 static uint32_t last; if(millis()-last>5000){last=millis();usb_host_lib_info_t i={};if(client)usb_host_lib_info(&i);Serial.printf("STATUS uptime=%lu devices=%d heap=%u\n",millis(),i.num_devices,ESP.getFreeHeap());}
}
