#include <rtthread.h>
#include "stm32f1xx_hal.h"
#include "ssd1306.h"

/* 传感器数据全局变量（供显示线程使用） */
static int8_t g_temperature = 0;
static uint8_t g_humidity = 0;
static uint8_t sensor_data_ready = 0;

/* 外部DHT11设备句柄声明 */
extern rt_device_t rt_hw_dht11_init(const char *name, struct rt_sensor_config *cfg);

/* 辅助函数：计算字符串像素宽度（Font_6x8 每个字符 6px） */
static uint16_t get_string_width(const char *str)
{
    return strlen(str) * 6;
}

/* OLED 显示任务入口：居中显示温度和湿度 */
static void oled_display_task_entry(void *parameter)
{
    char line1[24], line2[24], line3[24];
    uint16_t x1, x2, x3;
    int8_t temp;
    uint8_t humi;

    /* 初始化 OLED 屏幕 */
    ssd1306_Init();
    ssd1306_Fill(Black);
    ssd1306_UpdateScreen();
    rt_kprintf("[OLED] Display task started\n");

    while (1)
    {
        /* 获取最新的传感器数据 */
        rt_enter_critical();
        temp = g_temperature;
        humi = g_humidity;
        rt_exit_critical();

        /* 格式化显示内容（温度避免负数问题） */
        if (temp >= 0)
        {
            rt_sprintf(line1, "Temp:  %3d C", temp);
        }
        else
        {
            rt_sprintf(line1, "Temp: %3d C", temp);
        }
        rt_sprintf(line2, "Humi:  %3d %%", humi);
        rt_sprintf(line3, "DHT11  Running");

        /* 居中计算 */
        x1 = (128 - get_string_width(line1)) / 2;
        x2 = (128 - get_string_width(line2)) / 2;
        x3 = (128 - get_string_width(line3)) / 2;

        /* 更新屏幕 */
        ssd1306_Fill(Black);
        ssd1306_SetCursor(x1, 0);
        ssd1306_WriteString(line1, Font_6x8, White);
        ssd1306_SetCursor(x2, 16);
        ssd1306_WriteString(line2, Font_6x8, White);
        ssd1306_SetCursor(x3, 32);
        ssd1306_WriteString(line3, Font_6x8, White);

        ssd1306_UpdateScreen();

        /* 每秒刷新一次 */
        rt_thread_mdelay(1000);
    }
}

int main(void)
{
    /* OLED 显示线程句柄 */
    rt_thread_t oled_thread;

    rt_kprintf("\r\n");
    rt_kprintf("STM32F103 DHT11 Sensor System\r\n");
    rt_kprintf("==================================\r\n");
    rt_kprintf("System ready, DHT11 initializing...\r\n");

    /* 等待 DHT11 传感器设备初始化完成 */
    rt_thread_mdelay(2000);
    rt_kprintf("DHT11 sensor device check...\r\n");

    /* 创建 OLED 显示线程 */
    oled_thread = rt_thread_create("oled_show",
                                   oled_display_task_entry,
                                   RT_NULL,
                                   2048,
                                   20,
                                   10);
    if (oled_thread != RT_NULL)
    {
        rt_thread_startup(oled_thread);
        rt_kprintf("OLED display thread created!\r\n");
    }
    else
    {
        rt_kprintf("Failed to create OLED display thread!\r\n");
    }

    rt_kprintf("==================================\r\n");
    rt_kprintf("System ready!\r\n");
    rt_kprintf("Use 'ka_mqtt' command to start MQTT publish\r\n");

    return 0;
}
