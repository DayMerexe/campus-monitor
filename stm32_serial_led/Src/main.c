/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* MQTT 模式，无需 AT 指令，配置由 ESP8266 固件管理 */
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
char     rx_buf[64];
uint8_t  rx_idx = 0;
uint8_t  flame_alarm = 0;    // 火焰传感器报警（独立于 MQTT）
uint8_t  flame_debounce = 0; // 火焰防抖计数器
uint8_t  gate_open = 0;      // 闸门是否已开
uint8_t  mqtt_lv = 0;        // MQTT 上次下发的报警等级
uint8_t  mqtt_servo = 0;     // MQTT 上次下发的舵机指令
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
void servo_stop(void);
void servo_open_gate(void);
void servo_close_gate(void);
void servo_tick(void);
void set_outputs(int level);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();
  /* USER CODE BEGIN 2 */
  /* 手动初始化 PB8（蜂鸣器）*/
  {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin   = GPIO_PIN_8;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
  }

  /* PA0 火焰传感器输入 */
  {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin   = GPIO_PIN_0;
    GPIO_InitStruct.Mode  = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull  = GPIO_PULLUP;  /* 火焰传感器 DO 低电平有效 */
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
  }

  /* TIM3 PWM 舵机 (PA6) — 直接寄存器操作 */
  RCC->APB1ENR |= RCC_APB1ENR_TIM3EN;  /* 开 TIM3 时钟 */
  {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin       = GPIO_PIN_6;
    GPIO_InitStruct.Mode      = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed     = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
  }
  TIM3->PSC   = 128 - 1;           /* 64MHz/128 = 500kHz */
  TIM3->ARR   = 10000 - 1;         /* 500kHz/10000 = 50Hz  */
  TIM3->CCR1  = 750;               /* 1.5ms = 停止      */
  TIM3->CCMR1 = TIM_CCMR1_OC1M_1 | TIM_CCMR1_OC1M_2;  /* PWM 模式 1 */
  TIM3->CCER  = TIM_CCER_CC1E;     /* 使能 CH1 输出 */
  TIM3->CR1   = TIM_CR1_ARPE;      /* 自动重载预装载 */
  TIM3->CR1  |= TIM_CR1_CEN;       /* 启动定时器 */

  /* LED 默认关闭（RESET=亮, SET=灭，低电平有效） */
  HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, GPIO_PIN_SET);
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_RESET);  /* 蜂鸣器关 */

  /* 启动闪烁：DS2 红灯闪 3 次 */
  for (int i = 0; i < 3; i++) {
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_RESET);
    HAL_Delay(100);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_Delay(100);
  }

  /* 等待 ESP8266 完成 MQTT 初始化 */
  HAL_Delay(4000);

  /* 清空 USART2 缓冲区（ESP8266 启动时可能发的杂讯） */
  {
    uint8_t dump;
    while (HAL_UART_Receive(&huart2, &dump, 1, 2) == HAL_OK) {}
  }
  memset(rx_buf, 0, sizeof(rx_buf));
  rx_idx = 0;

  /* 黄灯闪 2 次，表示进入主循环 */
  for (int i = 0; i < 2; i++) {
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, GPIO_PIN_RESET);
    HAL_Delay(200);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_Delay(200);
  }

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    servo_tick();  /* 非阻塞舵机状态更新 */

    /* ── 火焰传感器检测（PA0，低电平有效）── */
    {
      static uint32_t last_flame_check = 0;
      uint32_t now = HAL_GetTick();
      if (now - last_flame_check >= 100) {  /* 每 100ms 检测一次 */
        last_flame_check = now;
        uint8_t raw = (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0) == GPIO_PIN_RESET);
        if (raw) {
          if (flame_debounce < 3) flame_debounce++;
          if (flame_debounce >= 3 && !flame_alarm) {
            flame_alarm = 1;
            set_outputs(2);        /* 红灯+蜂鸣器+黄灯 */
            servo_open_gate();
            HAL_UART_Transmit(&huart2, (uint8_t*)"FLAME:1\n", 8, 100);
          }
        } else {
          if (flame_debounce > 0) flame_debounce--;
          if (flame_debounce == 0 && flame_alarm) {
            flame_alarm = 0;
            set_outputs(mqtt_lv);  /* 恢复到 MQTT 上次状态 */
            if (mqtt_servo) servo_open_gate();
            else servo_close_gate();
            HAL_UART_Transmit(&huart2, (uint8_t*)"FLAME:0\n", 8, 100);
          }
        }
      }
    }

    /* ── MQTT 消息解析（USART2 ← ESP8266）── */
    uint8_t ch;
    if (HAL_UART_Receive(&huart2, &ch, 1, 1) == HAL_OK) {
      if (ch == '\r') {
        /* 忽略 */
      } else if (ch == '\n') {
        rx_buf[rx_idx] = '\0';
        if (rx_idx > 0) {
          int lv = 0, buz = 0, servo = 0;
          if (sscanf(rx_buf, "LV:%d,BUZ:%d,SERVO:%d", &lv, &buz, &servo) == 3) {
            mqtt_lv = lv;
            mqtt_servo = servo;
            if (!flame_alarm) {  /* 火焰报警优先级最高，不覆盖 */
              set_outputs(lv);
              if (servo) servo_open_gate();
              else servo_close_gate();
            }
          }
        }
        rx_idx = 0;
      } else {
        HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_5);  /* DS0 翻转 = 收到字节 */
        rx_buf[rx_idx++] = ch;
        if (rx_idx >= 63) rx_idx = 0;
      }
    }
  /* USER CODE END 3 */
  }
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI_DIV2;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL16;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */
/* ── 舵机控制（360° SG90, 50Hz PWM，非阻塞）── */
/* CCR: 250=正转全速, 750=停止, 1250=反转全速 */

static uint32_t servo_timer = 0;
static uint8_t  servo_state = 0;  /* 0=空闲, 1=开门中, 2=关门中 */
#define SERVO_DURATION 1200  /* 舵机动作持续 ms */

void servo_stop(void) {
  TIM3->CCR1 = 750;
}
void servo_open_gate(void) {
  return;  /* TODO: 演示前删除此行，恢复舵机功能（同时恢复火焰传感器舵机响应） */
  if (gate_open || servo_state) return;
  gate_open = 1;
  servo_state = 1;
  servo_timer = HAL_GetTick();
  TIM3->CCR1 = 300;
}
void servo_close_gate(void) {
  return;  /* TODO: 演示前删除此行，恢复舵机功能 */
  if (!gate_open || servo_state) return;
  gate_open = 0;
  servo_state = 2;
  servo_timer = HAL_GetTick();
  TIM3->CCR1 = 1200;
}
/* 在主循环中调用，非阻塞检查舵机是否完成 */
void servo_tick(void) {
  if (servo_state && (HAL_GetTick() - servo_timer >= SERVO_DURATION)) {
    servo_state = 0;
    TIM3->CCR1 = 750;
  }
}

/* ── 统一输出：LED + 蜂鸣器 ── */
void set_outputs(int level) {
  if (level == 0) {
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_RESET);
  } else if (level == 1) {
    HAL_GPIO_TogglePin(GPIOE, GPIO_PIN_5);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_RESET);
  } else {
    /* level == 2: 红色报警（蜂鸣器临时静音） */
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_RESET);  /* TODO: 演示前改回 SET */
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
