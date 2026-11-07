#pragma once
#include <stdbool.h>
#include <stddef.h>
#include "cJSON.h"
bool build_command_tool(const char *name,cJSON *args,char *destination,size_t capacity,char *error,size_t error_capacity);
const char *command_tools_json(void);
