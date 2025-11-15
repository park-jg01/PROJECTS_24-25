// ===============================
// Codevision, Atmega128
// ===============================
#include <mega128.h>
#include <stdio.h>
#include <lcd.h>
#include <delay.h>

#asm
    .equ __lcd_port = 0x15 ;
#endasm

#define ADC_VREF_TYPE 0x60 // 기준 전압: AVCC, ADC 데이터 좌측 정렬


int flag_sw0 = 0; //인터럽트 플래그
int flag_sw1 = 0; //인터럽트 플래그
unsigned char str[16]; // 크기가 16인 문자열 str 선언

unsigned char read_adc(unsigned char adc_input) // ADC Wizard 함수
{
    ADMUX = adc_input | (ADC_VREF_TYPE & 0xff); // 기준 전압 + 채널 선택
    delay_ms(1); // 안정화 시간 증가 (10us -> 1ms로 변경)
    ADCSRA |= 0x40; // ADC 변환 시작
    while ((ADCSRA & 0x10) == 0); // 변환 완료 대기
    ADCSRA |= 0x10; // 인터럽트 플래그 초기화
    return ADCH; //  ADCH을 통해 8비트 데이터를 읽음, return (ADCL | (ADCH << 8))- 10비트 데이터 반환
}

char Usart0_RX(void) { // 수신 함수 정의
    while(!(UCSR0A & 0x80)); // Receive Complete(수신 완료)까지 대기
    return UDR0; // UDR0의 Data를 반환
}

void main() {
    unsigned int joystick_value; //조이스틱 값 저장
    unsigned int left_speed, right_speed = 0;
    unsigned int add_speed = 0; //스피드 증가 변수  상태 저장
    
    unsigned int adc_on0, adc_off0, adc_value0;  // ADC0 측정 값 변수
    unsigned int adc_on1, adc_off1, adc_value1;  // ADC1 측정 값 변수
    unsigned int adc_on2, adc_off2, adc_value2;  // ADC2 측정 값 변수
    unsigned int adc_on3, adc_off3, adc_value3;  // ADC3 측정 값 변수
    unsigned int adc_on4, adc_off4, adc_value4;  // ADC4 측정 값 변수
    
    unsigned int threshold = 120;             // 검정/흰색 구분 임계값

    unsigned char adc_data; // ADC 데이터 저장을 위한 변수 adc_data 정의
    ADMUX = ADC_VREF_TYPE; // 기준 전압: AVCC, ADC 데이터 우측 정렬
    ADCSRA = 0x86; // ADC 활성화, 분주비 64
    
    //통신 설정
    UCSR0B = 0x18; // RX Enable                  0001 0000
    UCSR0C = 0x06; // 8Bit Data                  0000 0110
    UBRR0L = 0x67; // 0x67 = 103, 9600 Baud Rate 

    // PWM 초기화
    TCCR1A = (1 << WGM10) | (1 << COM1A1) | (1 << COM1B1);  // Fast PWM, 비반전 모드
    TCCR1B = (1 << WGM12) | (1 << CS11) | (1 << CS10);  // Prescaler 64
    
    // PB4 핀 출력 설정 (발광소자 제어용)
    DDRB |= (1 << DDB4);       // PB4 핀을 출력으로 설정
    PORTB &= ~(1 << DDB4);     // 초기 상태: LOW (발광소자 OFF) 
    
    // 모터 핀 설정
    DDRA |= (1 << DDA0) | (1 << DDA1) | (1 << DDA2) | (1 << DDA3);  // PA0, PA1, PA2, PA3 출력 설정 (모터 방향 핀)
    // 모터 방향 설정
    PORTA &= ~(1 << 0); // PA0 핀에 1 출력
    PORTA |= (1 << 1);  // PA1 핀에 0 출력
    PORTA &= ~(1 << 2); // PA2 핀에 1 출력
    PORTA |= (1 << 3);  // PA3 핀에 0 출력 

    DDRB |= (1 << DDB5) | (1 << DDB6); // PB5, PB6 PWM 출력 설정
     
    lcd_init(16); // LCD 초기화 (16자 사용)
    lcd_clear();  // LCD 화면 초기화

    while (1) {     
        joystick_value = Usart0_RX();
        
        //발광소자 켜기
        PORTB |= (1 << DDB4);        // 발광소자 ON
        delay_ms(10);                // 안정화 대기
        adc_on0 = read_adc(0);       // 반사광 측정
        adc_on1 = read_adc(1);       // 반사광 측정
        adc_on2 = read_adc(2);       // 반사광 측정
        adc_on3 = read_adc(3);       // 반사광 측정
        adc_on4 = read_adc(4);       // 반사광 측정

        //발광소자 끄기
        PORTB &= ~(1 << DDB4);       // 발광소자 OFF
        delay_ms(10);                // 안정화 대기
        adc_off0 = read_adc(0);      // 배경광 측정
        adc_off1 = read_adc(1);      // 배경광 측정
        adc_off2 = read_adc(2);      // 배경광 측정
        adc_off3 = read_adc(3);      // 배경광 측정
        adc_off4 = read_adc(4);      // 배경광 측정
        
        //반사광 계산 및 증폭
        adc_value0 = (adc_on0 > adc_off0) ? (adc_on0 - adc_off0) : 0;
        adc_value1 = (adc_on1 > adc_off1) ? (adc_on1 - adc_off1) : 0;
        adc_value2 = (adc_on2 > adc_off2) ? (adc_on2 - adc_off2) : 0;
        adc_value3 = (adc_on3 > adc_off3) ? (adc_on3 - adc_off3) : 0;
        adc_value4 = (adc_on4 > adc_off4) ? (adc_on4 - adc_off4) : 0;

        //색상 구분 및 모터 속도 제어
        lcd_gotoxy(0, 1);
        
        if (adc_value2 < threshold && adc_value1 >= threshold && adc_value3 >= threshold && adc_value0 >= threshold && adc_value4 >= threshold) {
        // 직진 (adc_value1만 임계값보다 작고, 나머지는 임계값 이상)
            left_speed = joystick_value;
            right_speed = joystick_value;
            sprintf(str, "Forward      BL");
        }
        else if (adc_value1 < threshold && adc_value2 < threshold && adc_value3 < threshold && adc_value0 >= threshold && adc_value4 >= threshold) {
            // 직진 (adc_value1, adc_value2, adc_value3만 임계값보다 작고, 나머지는 임계값 이상)
            left_speed = joystick_value;
            right_speed = joystick_value;
            sprintf(str, "Forward      BL");
        }  
        else if (adc_value0 < threshold && adc_value1 >= threshold && adc_value2 >= threshold && adc_value3 >= threshold && adc_value4 >= threshold) {
            // 좌회전 (adc_value0만 임계값보다 작고, 나머지는 임계값 이상)
            left_speed = joystick_value / 6;  // 더 급격히 회전
            right_speed = joystick_value;
            sprintf(str, "Turn Left    BL");
        } 
        else if (adc_value4 < threshold && adc_value0 >= threshold && adc_value1 >= threshold && adc_value2 >= threshold && adc_value3 >= threshold) {
            // 우회전 (adc_value4만 임계값보다 작고, 나머지는 임계값 이상)
            left_speed = joystick_value;
            right_speed = joystick_value / 6;  // 더 급격히 회전
            sprintf(str, "Turn Right   BL");
        } 
        else if (adc_value0 > threshold && adc_value1 > threshold && adc_value2 > threshold && adc_value3 > threshold && adc_value4 > threshold) {
            // 정지 (모든 센서 값이 임계값보다 큼)
            left_speed = 0;
            right_speed = 0;
            sprintf(str, "Stop         WH");
        }
           
        OCR1A = (left_speed > 255) ? 255 : (left_speed < 0) ? 0 : left_speed;
        OCR1B = (right_speed > 255) ? 255 : (right_speed < 0) ? 0 : right_speed;
        
        lcd_puts(str);
        delay_ms(100);
          
        //CLCD 출력       
        lcd_gotoxy(0, 0);//abc 값 출력
        sprintf(str, "%3d%3d%3d%3d%2d", adc_value0, adc_value1, adc_value2, adc_value3, adc_value4);
        lcd_puts(str);
        
        delay_ms(100);  
    }
}