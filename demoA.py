# BMF - V8 系列固件 A型固件
# 编写: Bei (LCH)
# 版本: 8代A型
# 修订: 第21次修订版
# 最后更新时间: 2025/4/29
# 差速前进技术: 是
# 多任务协同技术: 是
# PID相关支持: 是
# 高度保持相关支持: 是
# 左右手切换相关支持: 是
# 正式版本: 是
# 享受比赛,祝你好运 - 来自2025年 8thDCS - DCIC冠军队(作者)的祝愿
# 冠军队伍: 55861 - Digital China Innovation Contest 2025

import event, time, cyberpi, mbot2, gamepad, math

# initialize variables
Control_mode = 1
Status = 0
Status2 = 0
Status3 = 0
Status4 = 0

Kp_D = 0.90
Ki_D = 0.08
Kd_D = 1.20

Kp_DA = 4.0
Ki_DA = 0.2
Kd_DA = 0.01

Kp_AT = 1.5
Ki_AT = 0.0
Kd_AT = 0.8

# --------------------------------------Autonomous functions-------------------------------------------------

def clamp(var, min, max):  # 将var的值限制在min和max内
    if var < min:
        var = min
    if var > max:
        var = max
    return var

def DegClamp(angle): # 将角度angle转化为-180°-180°范围内 (确保PID转向以最短路径转向)
    if angle > 180:
        angle -= 360
    if angle < -180:
        angle += 360
    return angle

def PID_Turn(AngleX, SpeedX, TimeX):
    # 以不超过SpeedX的速度转弯AngleX°，并保证驱动时间不超过TimeX(s) 
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
      # 计算当前误差 (请注意,本机主控为垂直于地面倒装,请注意陀螺仪读数的正负性，即度数变化与正装时相反,且旋转时是绕着y轴旋转)
      error_angle = (AngleX - cyberpi.get_rotation('y')) 
      #计算PID中的积分项并限幅,防止积分饱和
      Integral_angle = Integral_angle + error_angle
      Integral_angle = clamp(Integral_angle, -300, 300)
      # 计算PID中微分项
      Derivative_angle = (error_angle - prev_error_angle)
      prev_error_angle = error_angle
      # 计算输出(位置式PID)
      Output_Angle = (Kp_AT * error_angle + ((Ki_AT * Integral_angle + Kd_AT * Derivative_angle)))
      # 处理输出值的正负性(如当前误差为20°[偏右20°],则Output为正值[符号与误差的符号相同],所以当L_Out=-Output,R_Out=Output时,左轮速度慢于右轮,向左转弯,修正误差)
      #这很重要,PID编写完整后请务必如上进行模拟确保符号正确性
      L_out = Output_Angle
      R_out = -Output_Angle
      L_out = clamp(L_out, -SpeedX, SpeedX)
      R_out = clamp(R_out, -SpeedX, SpeedX)
      mbot2.drive_power(L_out, -R_out)
      # 停止条件
      if math.fabs(error_angle) < 2:
        isDriving = 1
      time.sleep(0.02)
      
    mbot2.EM_stop("ALL")
    
def PID_Turn_Single(AngleX, SpeedX, TimeX):
    # 以不超过SpeedX的速度转弯AngleX°，并保证驱动时间不超过TimeX(s) 单电机转弯
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
    # 以不超过Speed的速度直行Distance距离，并保证驱动时间不超过Time(s) 增量式航向单环PID 已停用
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
    # 以不超过Speed的速度直行Distance距离，并保证驱动时间不超过Time(s) 增量式+位置式 航向距离 双环并联PID 精度±0.3cm
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
    while Count < 1:
        # 计算当前距离,注意左右电机对称安装,左电机往前为正,右电机往前为负
        current_distance = (cyberpi.mbot2.EM_get_angle("EM1") - cyberpi.mbot2.EM_get_angle("EM2")) / 2 
        # 计算距离和角度误差
        eA = DegClamp(cyberpi.get_rotation('y'))
        eD = Distance - current_distance
        # 计算距离和航向积分项
        EID += eD
        if math.fabs(eD) >= 100: EID = 0 # 误差过大时停用积分防止系统失控
        EID = clamp(EID, -0.8 * Distance, 0.8 * Distance)
        EDD = eD - eD_prev
        # 计算输出
        OutputA += (Kp_DA * (eA - eA_prev1)) + (Ki_DA * eA) + (Kd_DA * (eA - (2 * eA_prev1) + eA_prev2))
        OutputD = Kp_D * eD + Ki_D * EID + Kd_D * EDD
        # 对距离和航向输出进行限幅,保证速度不超过Speed,且为距离和航向环都预留一定的修正空间
        OutputA = clamp(OutputA, -0.10 * Speed, 0.10 * Speed)
        OutputD = clamp(OutputD, -0.90 * Speed, 0.90 * Speed)
        cyberpi.mbot2.drive_power(OutputD - OutputA, -(OutputD + OutputA))
        # 上一次误差prev_error的更新
        eA_prev2 = eA_prev1
        eA_prev1 = eA
        eD_prev = eD
        # 退出条件
        if math.fabs(eD) < 10 and math.fabs(eA) < 5: Count += 1
        else: Count = 0
        if cyberpi.timer.get() >= Time: break
        time.sleep(0.001)
    cyberpi.mbot2.EM_stop("ALL")
    
def UpdownAuto(Time, Speed):
    mbot2.motor_set(Speed,"M1")
    time.sleep(float(Time))
    mbot2.motor_set(0,"M1")
    

# --------------------------------------Drive Control functions-------------------------------------------------

def load():
    mbot2.servo_set(160,"S4")
    time.sleep(0.6)
    mbot2.servo_set(70,"S4")
    
def fire2():
    mbot2.servo_set(0,"S1")
    time.sleep(1.5)
    mbot2.servo_set(180,"S1") #无法发射调这里
    time.sleep(1.8)
    mbot2.servo_set(90,"S1") #无法复位到第二个齿调这里
    
def fire():
    mbot2.servo_set(180,"S1") #无法发射调这里
    time.sleep(1)
    mbot2.servo_set(90,"S1") #无法复位到第二个齿调这里
    
def Servo_Control():
    if gamepad.is_key_pressed('L1') or gamepad.is_key_pressed('R1'): #可加半自动一键转向吐球转回
      fire()
      load()
    elif gamepad.is_key_pressed('Select'):
      fire2()
      load()
    elif gamepad.is_key_pressed('Start'):
      load()
    elif gamepad.is_key_pressed('N2'):
      mbot2.servo_add(2,"S3")
    elif gamepad.is_key_pressed('N3'):
      mbot2.servo_add(-2,"S3")
    elif gamepad.is_key_pressed('N1'):
      mbot2.servo_add(2,"S2")
    elif gamepad.is_key_pressed('N4'):
      mbot2.servo_add(-2,"S2")
      
def Updown():
    global Status2, Status4
    if gamepad.is_key_pressed('Up'):
      mbot2.motor_set(-100,"M1")
      Status2 = 1
    elif gamepad.is_key_pressed('Down'):
      mbot2.motor_set(100,"M1")
      Status2 = 1
    elif gamepad.is_key_pressed('N2'):
        mbot2.motor_set(40,"M1")
        Status4 = 1
    elif gamepad.is_key_pressed('N3'):
        mbot2.motor_set(0,"M1")
        Status4 = 0    
    elif Status2 == 1 and not gamepad.is_key_pressed('Up') and not gamepad.is_key_pressed('Down') and Status4 == 0:
      mbot2.motor_set(0,"M1")
      Status2 = 0
      
def Intake():
    global Status
    if gamepad.get_joystick('Ry') > 30 or Status == 1:
      mbot2.motor_set(100,"M2")
      Status = 1
    if -30 > gamepad.get_joystick('Ry'):
      mbot2.motor_stop("M2")
      Status = 0
    if gamepad.is_key_pressed('N1'):
      mbot2.motor_set(-100,"M2")
      
def Intake2():
    global Status
    if gamepad.get_joystick('Ly') > 30 or Status == 1:
      mbot2.motor_set(100,"M2")
      Status = 1
    if -30 > gamepad.get_joystick('Ly'):
      mbot2.motor_stop("M2")
      Status = 0
    if gamepad.is_key_pressed('N1'):
      mbot2.motor_set(-100,"M2")
      
def Move():
    mbot2.drive_power(1 * ((gamepad.get_joystick('Ly') + gamepad.get_joystick('Lx'))), (-1 * 1) * ((gamepad.get_joystick('Ly') - gamepad.get_joystick('Lx'))))
    
def Move2():
    mbot2.drive_power(1 * ((gamepad.get_joystick('Ry') + gamepad.get_joystick('Rx'))), (-1 * 1) * ((gamepad.get_joystick('Ry') - gamepad.get_joystick('Rx'))))
    
def DriveControl():
    global Control_mode
    if Control_mode % 2 == 1:
      while True:
        Move()
        Intake()
        Servo_Control()
        Updown()
    else:
      while True:
        Move2()
        Intake2()
        Servo_Control()
        Updown()
    
## --------------------------------------Main-------------------------------------------------

@event.start
def on_start():
    # Init
    global Control_mode
    cyberpi.console.set_font(12)
    cyberpi.display.rotate_to(-90)
    cyberpi.display.show_label("B-M-F V8", 24, "center", index= 0)
    cyberpi.display.show_label("Bei MakeX Firmware V8A", 12, "bottom_mid", index= 1)
    cyberpi.audio.play_until('wake')
    mbot2.servo_drive(90,90,90,70)
    Control_mode = 0
    # Screen Control
    cyberpi.console.clear()
    cyberpi.console.println("Bei MakeX_Firmware V8A")
    cyberpi.console.println("Button 1 Drive Control")
    cyberpi.console.print("BAT1:")
    cyberpi.console.println(cyberpi.get_battery())
    cyberpi.console.print("BAT2:")
    cyberpi.console.println(cyberpi.get_extra_battery())
    # Choose Drive Control and Autonomous mode
    while True:
      if gamepad.is_key_pressed('Select'):
        Control_mode = Control_mode + 1
        time.sleep(0.5)

      if gamepad.is_key_pressed('N1'):
        time.sleep(0.5)
        DriveControl()
        
      if gamepad.is_key_pressed('N2') or gamepad.is_key_pressed('N3'):
        UpdownAuto(1.1,-100)
    
      if gamepad.is_key_pressed('N4'):
        AutonomousT()
        DriveControl()

      if cyberpi.controller.is_press("right"):
        AutonomousL()
        DriveControl()

      if cyberpi.controller.is_press("left"):
        AutonomousR()
        DriveControl()
      
      if cyberpi.controller.is_press("up"):
        UpdownAuto(1.3,-100)

@event.is_press('a')
def is_btn_press():
    cyberpi.restart()

# --------------------------------------Autonomous Code-------------------------------------------------

def AutonomousL():
    PID_Turn_Single(25,100,1)
    PID_Drive_X(2400,100,2)
    UpdownAuto(0.2,100)
    PID_Drive_X(400,-95,1)
    PID_Turn(-90,100,1)
    PID_Drive(375,100,2)
    PID_Turn(90,100,1)
    PID_Drive(500,100,2)
    UpdownAuto(1.5,100)
    mbot2.motor_set(100,"M2")
    UpdownAuto(0.1,-100)
    PID_Drive(-200,100,1)
    UpdownAuto(1,-100)
    PID_Drive(-400,100,2)
    PID_Turn(90,100,1)
    UpdownAuto(1,100)
    PID_Drive(1000,50,2)
    mbot2.motor_stop("all")
    
def AutonomousR():
    PID_Turn_Single(-25,100,1)
    PID_Drive_X(2400,100,2)
    UpdownAuto(0.2,100)
    PID_Drive_X(400,-95,1)
    PID_Turn(90,100,1)
    PID_Drive(375,100,2)
    PID_Turn(-87,100,1)
    PID_Drive(500,100,2)
    UpdownAuto(1.5,100)
    mbot2.motor_set(100,"M2")
    UpdownAuto(0.1,-100)
    PID_Drive(-200,100,1)
    UpdownAuto(1,-100)
    PID_Drive(-300,100,2)
    PID_Turn(-90,100,1)
    UpdownAuto(1,100)
    PID_Drive(1000,50,2)
    mbot2.motor_stop("all")
    
def AutonomousT():
    pass

    

