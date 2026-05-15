/*
 * Copyright (c) 2006-2025, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2025-04-22     RT-Thread    first version
 * 2025-05-11     Modified     Refactored with modular design
 */

/* RT-Thread 核心库 */
#include <rtthread.h>
#include <rtdbg.h>
#include <rtdevice.h>

/* 硬件驱动 */
#include "board.h"
#include "drv_common.h"
#include "adc.h"
#include "dma.h"

/* 网络协议栈 */
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

/* 外设驱动 */
#include "ssd1306.h"
#include "ssd1306_fonts.h"
#include "sensor_dallas_dht11.h"

/* 物联网协议 */
#include "mqttclient.h"
#include "cJSON.h"

/* 调试配置 */
#define DBG_TAG "main"
#define DBG_LVL DBG_LOG

/* 硬件引脚定义 */
#define KEY0_PIN    GET_PIN(E, 4)
#define KEY1_PIN    GET_PIN(E, 3)
#define LED0_PIN    GET_PIN(B, 5)
#define LED1_PIN    GET_PIN(E, 5)
#define DHT11_DATA_PIN    GET_PIN(G, 11)

/* 网络参数 */
#define SERVER_IP   "192.168.64.171"
#define SERVER_PORT 8080
#define ADC_BUFFER_SIZE 50

/* MQTT 参数 */
#define KAWAII_MQTT_HOST      "jiejie01.top"
#define KAWAII_MQTT_PORT      "1883"
#define KAWAII_MQTT_CLIENTID  "rtthread001"
#define KAWAII_MQTT_USERNAME  "rt-thread"
#define KAWAII_MQTT_PASSWORD  "rt-thread"
#define KAWAII_MQTT_PUBTOPIC  "rtt-pub"

/* ADC 数据缓冲区 */
static int16_t adc_buffer[ADC_BUFFER_SIZE];

/* 传感器数据 */
uint8_t g_temperature = 0;    // 当前温度值
uint8_t g_humidity = 0;       // 当前湿度值

/* 系统状态 */
volatile int mode = 0;        // 0:自动上传, 1:手动上传
volatile int key1_upload_flag = 0; // 手动上传触发标志

/* MQTT 客户端实例 */
static mqtt_client_t *g_mqtt_client = RT_NULL;

/**
 * @brief 初始化LED引脚
 */
static void led_init(void)
{
    rt_pin_mode(LED0_PIN, PIN_MODE_OUTPUT);
    rt_pin_mode(LED1_PIN, PIN_MODE_OUTPUT);
    rt_pin_write(LED0_PIN, PIN_HIGH); // 默认熄灭
    rt_pin_write(LED1_PIN, PIN_HIGH);
}

/**
 * @brief 控制LED状态
 * @param cmd 控制命令（如 "led0 on", "led1 off"）
 */
static void led_control(const char *cmd)
{
    if (rt_strncmp(cmd, "led0 on", 7) == 0)
        rt_pin_write(LED0_PIN, PIN_LOW);
    else if (rt_strncmp(cmd, "led0 off", 8) == 0)
        rt_pin_write(LED0_PIN, PIN_HIGH);
    else if (rt_strncmp(cmd, "led1 on", 7) == 0)
        rt_pin_write(LED1_PIN, PIN_LOW);
    else if (rt_strncmp(cmd, "led1 off", 8) == 0)
        rt_pin_write(LED1_PIN, PIN_HIGH);
}

// 按键控制模块
static void key_init(void)
{
    rt_pin_mode(KEY0_PIN, PIN_MODE_INPUT);
    rt_pin_mode(KEY1_PIN, PIN_MODE_INPUT);
}

// 按键回调
static void key0_callback(void *args)
{
    mode = !mode;
    if (mode == 0)
        rt_pin_write(LED0_PIN, PIN_LOW); // LED0 on
    else
        rt_pin_write(LED0_PIN, PIN_HIGH); // LED0 off
    rt_kprintf("KEY0 switched, now: %s\n", mode == 0 ? "auto" : "manual");
}

static void key1_callback(void *args)
{
    if (mode == 1)
    {
        key1_upload_flag = 1; // 只设置标志位，不做实际上传
    }
}

static void key_enable_irq(void)
{
    rt_pin_attach_irq(KEY0_PIN, PIN_IRQ_MODE_FALLING, key0_callback, RT_NULL);
    rt_pin_irq_enable(KEY0_PIN, PIN_IRQ_ENABLE);
    rt_pin_attach_irq(KEY1_PIN, PIN_IRQ_MODE_FALLING, key1_callback, RT_NULL);
    rt_pin_irq_enable(KEY1_PIN, PIN_IRQ_ENABLE);
}

// ADC 采集模块
static void adc_init(void)
{
    // 初始化DMA和ADC
    MX_DMA_Init();
    MX_ADC3_Init();

    // 启动ADC的DMA传输
    HAL_NVIC_DisableIRQ(DMA2_Channel4_5_IRQn); // 禁用DMA中断
    HAL_ADC_Start_DMA(&hadc3, (rt_uint32_t*)adc_buffer, ADC_BUFFER_SIZE);
}

static float adc_get_voltage(void)
{
    // 返回第一个ADC采样值转换后的电压
    return adc_buffer[0] / 4095.0f * 3.3f;
}

// DHT11采集函数
static void dht11_sample_thread(void *parameter)
{
    rt_base_t dht11_pin = DHT11_DATA_PIN;
    dht11_init(dht11_pin);
    while (1)
    {
        int32_t value = dht11_get_temperature(dht11_pin);
        g_temperature = (value & 0xFFFF);
        g_humidity = (value >> 16) & 0xFF;
        rt_thread_mdelay(1000);
    }
}

// OLED显示线程
static void oled_display_thread(void *parameter)
{
    ssd1306_Init();
    while (1)
    {
        char buf[32];
        ssd1306_Fill(Black);
        rt_snprintf(buf, sizeof(buf), "Temp: %d C", g_temperature);
        ssd1306_SetCursor(0, 0);
        ssd1306_WriteString(buf, Font_7x10, White);
        rt_snprintf(buf, sizeof(buf), "Humi: %d %%", g_humidity);
        ssd1306_SetCursor(0, 12);
        ssd1306_WriteString(buf, Font_7x10, White);
        ssd1306_SetCursor(0, 24);
        ssd1306_WriteString(mode == 0 ? "mode:auto" : "mode:manual", Font_7x10, White);
        ssd1306_UpdateScreen();
        rt_thread_mdelay(1000);
    }
}

// MQTT上传线程
static void mqtt_upload_thread(void *parameter)
{
    // 1. 初始化MQTT客户端
    mqtt_log_init();
    g_mqtt_client = mqtt_lease();
    mqtt_set_host(g_mqtt_client, KAWAII_MQTT_HOST);
    mqtt_set_port(g_mqtt_client, KAWAII_MQTT_PORT);
    mqtt_set_user_name(g_mqtt_client, KAWAII_MQTT_USERNAME);
    mqtt_set_password(g_mqtt_client, KAWAII_MQTT_PASSWORD);
    mqtt_set_client_id(g_mqtt_client, KAWAII_MQTT_CLIENTID);
    mqtt_set_clean_session(g_mqtt_client, 1);

    // 2. 连接服务器
    int ret = mqtt_connect(g_mqtt_client);
    if (ret != 0) {
        rt_kprintf("MQTT连接失败，错误码: %d\n", ret);
        while (1) rt_thread_mdelay(5000); // 阻塞重试
    } else {
        rt_kprintf("MQTT连接成功！\n");
    }

    // 3. 主循环
    while (1) {
        if (mode == 0) {
            // 自动上传模式
            cJSON *root = cJSON_CreateObject();
            cJSON_AddNumberToObject(root, "temperature", g_temperature);
            cJSON_AddNumberToObject(root, "humidity", g_humidity);
            char *json_str = cJSON_PrintUnformatted(root);
            cJSON_Delete(root);

            if (json_str) {
                mqtt_message_t msg = {0};
                msg.qos = QOS0;
                msg.payload = json_str;
                msg.payloadlen = strlen(json_str);
                mqtt_publish(g_mqtt_client, KAWAII_MQTT_PUBTOPIC, &msg);
                rt_kprintf("au: %s\n", json_str);
                free(json_str);
            }
            rt_thread_mdelay(3000);
        } else {
            // 手动上传模式
            if (key1_upload_flag) {
                key1_upload_flag = 0;
                cJSON *root = cJSON_CreateObject();
                cJSON_AddNumberToObject(root, "temperature", g_temperature);
                cJSON_AddNumberToObject(root, "humidity", g_humidity);
                char *json_str = cJSON_PrintUnformatted(root);
                cJSON_Delete(root);

                if (json_str) {
                    mqtt_message_t msg = {0};
                    msg.qos = QOS0;
                    msg.payload = json_str;
                    msg.payloadlen = strlen(json_str);
                    mqtt_publish(g_mqtt_client, KAWAII_MQTT_PUBTOPIC, &msg);
                    rt_kprintf("ma: %s\n", json_str);
                    free(json_str);
                }
            }
            rt_thread_mdelay(100);
        }
    }
}

int main(void)
{
    rt_pin_mode(GET_PIN(B,12), PIN_MODE_OUTPUT);
    // 硬件初始化
    led_init();
    key_init();
    adc_init();
    key_enable_irq();

    // 启动所有线程
    rt_thread_t tid_dht11 = rt_thread_create("dht11", dht11_sample_thread, RT_NULL, 1024, 15, 10);
    rt_thread_t tid_oled = rt_thread_create("oled", oled_display_thread, RT_NULL, 1024, 16, 10);
    rt_thread_t tid_mqtt = rt_thread_create("mqtt", mqtt_upload_thread, RT_NULL, 2048, 17, 10);

    if (tid_dht11) rt_thread_startup(tid_dht11);
    if (tid_oled) rt_thread_startup(tid_oled);
    if (tid_mqtt) rt_thread_startup(tid_mqtt);

    // 主循环
    while (1) {
        rt_thread_mdelay(1000);
    }
    return RT_EOK;
}
