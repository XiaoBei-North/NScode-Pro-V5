# BMF - V8 系列固件 B型固件
# 编写: Bei (LCH)
# 版本: 8代B型
# 修订: 第33次修订版
# 最后更新时间: 2025/4/30
# 差速前进技术: 是
# 多任务协同技术: 是
# PID相关支持: 是
# 高度保持相关支持: 否
# 左右手切换相关支持: 是
# 正式版本: 是
# 享受比赛,祝你好运 - 来自2025年 8thDCS - DCIC冠军队(作者)的祝愿
# 冠军队伍: 55861 - Digital China Innovation Contest 2025

import event, time, cyberpi, mbot2, gamepad, math, mbuild
import time
# initialize variables
Status2 = 0

Kp_D = 0.50
Ki_D = 0.08
Kd_D = 1.00

Kp_DA = 4.0
Ki_DA = 0.2
Kd_DA = 0.01

Kp_AT = 1.30
Ki_AT = 0.05
Kd_AT = 0.90

# --------------------------------------Autonomous functions-------------------------------------------------

def clamp(var, min, max):
    if var < min:
        var = min
    if var > max:
        var = max
    return var

def DegClamp(angle):
    if angle > 180:
        angle -= 360
    if angle < -180:
        angle += 360
    return angle

def PID_Turn(AngleX, SpeedX, TimeX):
    # 以不超过Speed的速度向左或向右转Angle度，并确保驱动时间不超过Time
    # Angle : 转向角度
    #   当angle>0时，向右转angle°
    #   当angle<0时，向左转angle°
    global Kp, Ki, Kd, Kp_A, Ki_A, Kd_A
    Integral_angle = 0
    Derivative_angle = 0
    error_angle = 0
    prev_error_angle = 0
    Output_Angle = 0
    isDriving = 0
    L_out = 0
    R_out = 0
    cyberpi.reset_rotation('all')
    cyberpi.timer.reset()
    
    while not (cyberpi.timer.get() > TimeX or isDriving == 1):
      error_angle = (AngleX + cyberpi.get_rotation('y'))
      Integral_angle = Integral_angle + error_angle
      Integral_angle = clamp(Integral_angle, -300, 300)
      Derivative_angle = (error_angle - prev_error_angle)
      prev_error_angle = error_angle
      Output_Angle = (Kp_AT * error_angle + ((Ki_AT * Integral_angle + Kd_AT * Derivative_angle)))
      L_out = Output_Angle
      R_out = -Output_Angle
      L_out = clamp(L_out, -SpeedX, SpeedX)
      R_out = clamp(R_out, -SpeedX, SpeedX)
      mbot2.drive_power(L_out, -R_out)
      if math.fabs(error_angle) < 2:
        isDriving = 1
      time.sleep(0.02)
      
    mbot2.EM_stop("ALL")
    
def PID_Turn_Single(AngleX, SpeedX, TimeX):
    global Kp_AT, Ki_AT, Kd_AT
    Integral_angle = 0
    Derivative_angle = 0
    error_angle = 0
    prev_error_angle = 0
    Output_Angle = 0
    isDriving = 0
    L_out = 0
    R_out = 0
    cyberpi.reset_rotation('all')
    cyberpi.timer.reset()
    
    while not (cyberpi.timer.get() > TimeX or isDriving == 1):
      error_angle = (AngleX - cyberpi.get_rotation('y'))
      Integral_angle = Integral_angle + error_angle
      Integral_angle = clamp(Integral_angle, -300, 300)
      Derivative_angle = (error_angle - prev_error_angle)
      prev_error_angle = error_angle
      Output_Angle = (Kp_AT * error_angle + ((Ki_AT * Integral_angle + Kd_AT * Derivative_angle)))
      Output_Angle = clamp(Output_Angle, -SpeedX, SpeedX)
      if AngleX > 0 :
        mbot2.drive_power(Output_Angle, 0)
      else:
        mbot2.drive_power(0, Output_Angle)  
      if math.fabs(error_angle) < 2:
        isDriving = 1
      time.sleep(0.02)
      
    mbot2.EM_stop("ALL")

def PID_Drive_X(Distance, Speed, Time):
    # 以不超过Speed的速度直行Distance距离，并保证驱动时间不超过Time(s) 增量式航向单环PID 
    global Kp_DA, Ki_DA, Kd_DA
    e_1 = 0
    e_2 = 0
    current_distance = 0
    Output = 0
    cyberpi.mbot2.EM_reset_angle("ALL")
    cyberpi.reset_rotation("all")
    cyberpi.timer.reset()
    while current_distance < Distance and cyberpi.timer.get() < Time:
        current_distance = (cyberpi.mbot2.EM_get_angle("EM1") - cyberpi.mbot2.EM_get_angle("EM2")) / 2
        e_0 = DegClamp(cyberpi.get_rotation('y'))
        Output += (Kp_DA * (e_0 - e_1)) + (Ki_DA * e_0) + (Kd_DA * (e_0 - (2 * e_1) + e_2))
        cyberpi.mbot2.drive_power(Speed - Output, -(Speed + Output))
        e_2 = e_1
        e_1 = e_0
    cyberpi.mbot2.EM_stop("ALL")
    
def PID_Drive(Distance, Speed, Time):
    # 以不超过Speed的速度直行Distance距离，并保证驱动时间不超过Time(s) 增量式+位置式 航向距离 双环PID 精度±0.1cm
    global Kp_DA, Ki_DA, Kd_DA, Kp_D, Ki_D, Kd_D
    Count = 0
    eA_prev1 = 0       
    eA_prev2 = 0
    OutputA = 0
    EID = 0
    eD_prev = 0
    Count = 0
    cyberpi.mbot2.EM_reset_angle("ALL")
    cyberpi.reset_rotation("all")
    cyberpi.timer.reset()
    while Count < 3:
        current_distance = (cyberpi.mbot2.EM_get_angle("EM1") - cyberpi.mbot2.EM_get_angle("EM2")) / 2
        eA = DegClamp(cyberpi.get_rotation('y'))
        eD = Distance - current_distance
        EID += eD
        if math.fabs(eD) >= 100: EID = 0
        EID = clamp(EID, -0.8 * Distance, 0.8 * Distance)
        EDD = eD - eD_prev
        OutputA += (Kp_DA * (eA - eA_prev1)) + (Ki_DA * eA) + (Kd_DA * (eA - (2 * eA_prev1) + eA_prev2))
        OutputD = Kp_D * eD + Ki_D * EID + Kd_D * EDD
        OutputA = clamp(OutputA, -0.10 * Speed, 0.10 * Speed)
        OutputD = clamp(OutputD, -0.90 * Speed, 0.90 * Speed)
        cyberpi.mbot2.drive_power(OutputD + OutputA, -(OutputD - OutputA))
        eA_prev2 = eA_prev1
        eA_prev1 = eA
        eD_prev = eD
        if math.fabs(eD) < 10 and math.fabs(eA) < 3: Count += 1
        else: Count = 0
        if cyberpi.timer.get() >= Time: break
        time.sleep(0.001)
    cyberpi.mbot2.EM_stop("ALL")
    
def Camera_Aim(Time,Target):
    #机器视觉自动锁定锥桶
    #PixyMon Signature 1 range : 4.0
    cyberpi.timer.reset()
    mbuild.smart_camera.set_mode("color", 1)
    mbuild.smart_camera.set_kp(0.5, 1)
    while cyberpi.timer.get() < Time:
      if mbuild.smart_camera.get_sign_x(1, 1) > (Target - 10) and mbuild.smart_camera.get_sign_x(1, 1) < (Target + 10):
        mbot2.drive_speed(0,0)
      else:
        X = mbuild.smart_camera.get_sign_diff_speed(1, 'x', Target, 1)
        mbot2.drive_speed(-X, -X)

def UpdownAuto(Time, Speed):
    mbot2.motor_set(Speed,"M1")
    time.sleep(float(Time))
    mbot2.motor_set(0,"M1")

# ---------------------------------------------Drive Control Functions------------------------------------------

def Servo_Control():
    if gamepad.is_key_pressed('N4'):
      mbot2.servo_set(0,"S2") #爪子开合半自动
    elif gamepad.is_key_pressed('N1'):
      mbot2.servo_set(160,"S2") #爪子开合半自动
    elif gamepad.is_key_pressed('Up'):
      mbot2.servo_add(-2,"S4")
    elif gamepad.is_key_pressed('Down'):
      mbot2.servo_add(2,"S4")
    elif gamepad.is_key_pressed('R1'): #可改半自动 (自动上膛)
      mbot2.servo_set(20,"S3")
      time.sleep(1)
      mbot2.servo_set(170,"S3")
      time.sleep(0.8)
      mbot2.servo_set(145,"S3")
    elif gamepad.is_key_pressed('L1'):
      mbot2.servo_set(90,"S3")
    elif gamepad.is_key_pressed('Left'):
      mbot2.servo_set(0,"S1")
    elif gamepad.is_key_pressed('Right'):
      mbot2.servo_set(35,"S1")
    elif gamepad.is_key_pressed('L_Thumb'):
      mbot2.servo_set(110,"S4")
    elif gamepad.is_key_pressed('R_Thumb'):
      Camera_Aim(1,200)
      
def Updown():
    global Status2
    if gamepad.is_key_pressed('N2'):
      mbot2.motor_set(100,"M1")
      Status2 = 1
    elif gamepad.is_key_pressed('N3'):
      mbot2.motor_set(-100,"M1")
      Status2 = 1
    elif Status2 == 1:
      mbot2.motor_set(0,"M1")
      Status2 = 0
      
def Intake():
    if gamepad.get_joystick('Ry') > 30:
      mbot2.motor_set(100,"M2")
    elif -30 > gamepad.get_joystick('Ry'):
      mbot2.motor_set(0,"M2")
    elif gamepad.is_key_pressed('Select'):
      mbot2.motor_set(-100,"M2")
      
def Move():
        mbot2.drive_power(1 * ((gamepad.get_joystick('Ly') + gamepad.get_joystick('Lx'))), (-1 * 1) * ((gamepad.get_joystick('Ly') - gamepad.get_joystick('Lx'))))
    
def Move2():
    mbot2.drive_power(0.4 * ((gamepad.get_joystick('Ry') + gamepad.get_joystick('Rx'))), (-1 * 0.4) * ((gamepad.get_joystick('Ry') - gamepad.get_joystick('Rx'))))
    
# ---------------------------------------------Main----------------------------------------------------------

@event.start
def on_start():
    mbuild.smart_camera.reset(1)
    time.sleep(5)
    cyberpi.console.set_font(12)
    cyberpi.display.show_label("B-M-F V8", 24, "center", index= 0)
    cyberpi.display.show_label("Bei MakeX Firmware V8B", 12, "bottom_mid", index= 1)
    cyberpi.audio.play_until('wake')
    mbot2.servo_drive(0,0,140,20)
    cyberpi.console.clear()
    cyberpi.console.println("Bei MakeX_Firmware V8B")
    cyberpi.console.println("Button 1 Drive Control")
    cyberpi.console.println("Button 2 Autonomous")
    cyberpi.console.print("BAT1:")
    cyberpi.console.println(cyberpi.get_battery())
    cyberpi.console.print("BAT2:")
    cyberpi.console.println(cyberpi.get_extra_battery())
    while True:
      if gamepad.is_key_pressed('N1'):
        DriveControl()
        
      if gamepad.is_key_pressed('N2') or gamepad.is_key_pressed('N3'):
        UpdownAuto(0.2,100)
        
      if gamepad.is_key_pressed('N4'):
        AutonomusT()
        DriveControl()

      if cyberpi.controller.is_press("left"):
        AutonomousL()
        DriveControl()

      if cyberpi.controller.is_press("right"):
        AutonomusR()
        DriveControl()

def DriveControl():
    while True:
      Move()
     # Move2()
      Intake()
      Servo_Control()
      Updown()

@event.is_press('a')
def is_btn_press():
    cyberpi.restart()

# ---------------------------------------------Autonomous Code--------------------------------------------

def AutonomousL():
    mbot2.servo_drive(0,160,140,110)
    PID_Drive(1850,100,2)
    mbot2.servo_set(0,"S2")
    time.sleep(10)
    UpdownAuto(1,100)
    #mbot2.servo_add(-65,"S4")
    time.sleep(0.3)
    PID_Drive(-500,100,1)
    time.sleep(0.3)
    PID_Turn(-180,100,2)
    PID_Drive(600,100,1) 
    mbot2.servo_add(65,"S4")
    mbot2.servo_set(160,"S2")
    PID_Drive(-400,100,1)
    PID_Turn(-90,100,1.5)
    PID_Drive(1300,100,2)
    PID_Turn(-80,100,1)
    '''
    time.sleep(1)
    Camera_Aim(1,150)
    cyberpi.console.println(mbuild.smart_camera.get_sign_x(1, 1))
    PID_Drive(1000,100,2.5) 
    mbot2.servo_set(0,"S2")
    PID_Turn(-20,100,1)
    time.sleep(0.5)
    UpdownAuto(3,100)
    mbot2.servo_add(-60,"S4")
    time.sleep(0.3)
    PID_Turn(45,100,1)
    PID_Drive(-400,100,1.5)
    UpdownAuto(0.9,-100)
    mbot2.servo_add(60,"S4")
    time.sleep(0.3)
    mbot2.servo_set(150,"S2")  
    time.sleep(0.4)
    PID_Turn(-180,100,2)
    '''
    pass

def AutonomusR():
    # DO SOMETHING
    mbot2.servo_drive(0,160,140,110)
    UpdownAuto(0.2,100)
    PID_Drive(1850,100,2)
    mbot2.servo_set(0,"S2")
    time.sleep(6)
    UpdownAuto(1,100)
    #mbot2.servo_add(-65,"S4")
    time.sleep(0.3)
    PID_Drive(-500,100,1)
    time.sleep(0.3)
    PID_Turn(-180,100,2)
    PID_Drive(600,100,1) 
    mbot2.servo_add(65,"S4")
    mbot2.servo_set(160,"S2")
    PID_Drive(-400,100,1)
    PID_Turn(-90,100,1.5)
    PID_Drive(1300,100,2)
    PID_Turn(-80,100,1)
    pass

def AutonomusT():
    UpdownAuto(0.3,-100)
    PID_Drive(1850,100,3)
    mbot2.servo_set(0,"S2")
    time.sleep(0.3)
    UpdownAuto(0.9,100)
    PID_Drive(-300,100,1)
    #time.sleep(0.3)
    PID_Turn(-150,100,2) #Speed 80 Time 3
    PID_Drive(600,100,1) 
    UpdownAuto(0.6,-100)
    mbot2.servo_set(110,"S2")
    PID_Drive(-200,100,1)
    PID_Turn(-55,100,1.5) #Speed 80
    #time.sleep(1)
    Camera_Aim(2,200) 
    PID_Drive(900,100,2) 
    mbot2.servo_set(0,"S2")
    time.sleep(0.5)
    UpdownAuto(3,100)
    mbot2.servo_add(-60,"S4")
    time.sleep(0.3)
    PID_Turn(45,100,1)
    PID_Drive(-400,100,1.5)
    UpdownAuto(0.9,-100)
    mbot2.servo_add(60,"S4")
    time.sleep(0.3)
    mbot2.servo_set(150,"S2")  
    pass
