#pragma once
#include <stdbool.h>
#include <stddef.h>

#define PHONE_COMMAND_CAPACITY 4096
#define PHONE_TEXT_CAPACITY 32768
typedef struct { bool truncated;size_t total_received;char tail[128];size_t tail_size;bool ok;bool connected;size_t size;unsigned char *image;char text[PHONE_TEXT_CAPACITY];char error[128];long elapsed_ms; } phone_result_t;
extern phone_result_t phone_result;
bool phone_execute(const char *command,bool screenshot);
void network_start(void);
