开发日志:
1. 2026.4.13:
目标；水位传感器的添加

水位传感器连接PA7_ADC1

创建RTT与创建CUBEMX文件:(第一次创建CUBEMX需要退出CUBEMX才行)
水位传感器用PA7为ADC1_INPUT模式，通过串口来将数据传输到电脑窗口
时钟树设置:使用外部晶振配置(RCC),HSE=8MHZ,Enable CSS APB1进行除2 注意:ADC 进行/6的分频
打开UART

2.2026.4.16:
目标:连接WIFI MQTT

使用UART3连接WIFI
sty的MQTT输出规范：{
    temp:   //温度
    level:  //水位
    tds:  //浑浊度
}

plq的MQTT输出规范:{
    level:  //水位   单位:百分比
    speed:  //速度
    wet:  //湿度    单位:百分比
}

MQTT接收:{
    led
    蜂鸣器(beep)
    继电器(relay)
    舵机(motor)
}



WIFI使用RTT软件第三方库，需注释:
搜索:AT+CIPDNS；注释at_device_esp8266.c 104行与307行

AT+CIPSTART

第一共同版本:mom.zip





2026.4.17:
PC4  -> 风速传感器
PC5  -> 土壤湿度传感器