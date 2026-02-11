import RPi.GPIO as GPIO
from flask import Flask, jsonify, request
import board
import adafruit_dht
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15
import threading
import time
import pwmio
import requests
import json
import math

#startup, objek-objek dan variabel global
print("Program start")
url="https://script.google.com/macros/s/AKfycbwxFlHaoqamaUDAk16_cWcRXTKTpjYQpA0FLyjOhJd09-gYS_ogDMbPMKrcctN3wZxRrA/exec"
i2cadr = 0x48 #atau 0x4a?
i2c = board.I2C()
i2cstatus=0
try:
  ads = ADS1115(i2c, address=i2cadr)
  i2cstatus=1
except:
  pass

if i2cstatus==0:
  i2cadr=0x4a
  try:
    ads = ADS1115(i2c, address=i2cadr)
    i2cstatus=1
  except:
    pass

pinLED = [6,13,15] #merah,hijau,pompa (active high)
pinLEDstrip = 18 #PWM output
#pinpompa = 15 #active high

print("Setting GPIO")
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
#set semua pin output dengan 1 perintah ini
[GPIO.setup(p,GPIO.OUT) for p in pinLED]
#set semua pin output low
[GPIO.output(p, GPIO.LOW) for p in pinLED]

print("setup PWM")
ledpwm = pwmio.PWMOut(board.D18,frequency=1000,duty_cycle=0)

#sensor apa yang terpasang di A0 dan A1?
print("setup ADS1115")
ch0 = AnalogIn(ads, ads1x15.Pin.A0)
ch1 = AnalogIn(ads, ads1x15.Pin.A1)

#DHT11
print("setup DHT11")
dht = adafruit_dht.DHT11(board.D4)

#variabel untuk menyimpan segala data dan status
status={"dht":0, "ADS": 0, "time": 0, "pwmout": 0, "pump": 0, "led": 0,"sudah_nyiram": False, "menit_terakhir": 0, "percentage_led":0}
sensordata={"A0":0, "A1": 0, "temp": 0, "humid": 0}
settings={"interval":2, "report_update": 300, "running": 1, "kering":26556, "basah":14949, "lux_min":15000, "lux_max":30000, "durasi_max_pump":10}
jadwal=[]

#thread lock untuk mencegah tabrakan antara thread measurement dan server mengakses data
datalock = threading.Lock()
jadwallock= threading.Lock()

#server
print("setup server")
myapp = Flask(__name__)

#web pages
@myapp.route('/')
def tampil_mainpage():
  print("Server> main page requested")
  return myapp.send_static_file('index.html')

@myapp.route('/data')
def senddata():
  print("Server> data requested")
  s = ""
  with datalock: #.acquire():
    s = jsonify(sensordata)
  return s

@myapp.route('/status')
def sendstatus():
  print("Server> status requested")
  s = ""
  with datalock: #.acquire():
    s = jsonify(status)
  return s

@myapp.route('/settings')
def changeset():
  ru = request.args.get('ru')
  if ru is not None and int(ru) > 5:
    with datalock:
      settings["report_update"]=int(ru)
    print("Report update> changed")
  restart = request.args.get('restart')
  if restart is not None and restart == 'y':
    with datalock:
      settings["running"]=0

  with datalock:
    s = jsonify(settings)
  return s

@myapp.route('/jadwal')
def inputjadwal():
  t = request.args.get('t')
  a = request.args.get('a')
  if t is not None and a is not None:
    j = {"t":t, "a": a}
    print("tambah jadwal>", j)
    with jadwallock:
      jadwal.append(j)
    return jsonify(j)
  s = request.args.get('save')
  if s is not None:
    print("save>", s)
    savejadwal(s)
    return "OK"
  l = request.args.get('load')
  if l is not None:
    print("load>", l)
    bukajadwal(l)
    return "OK"
#kalau sampai sini berarti tidak ada parameter
  print("tidak ada param")
  resp = ""
  with jadwallock:
    for j in jadwal:
      print(j)
      resp+=json.dumps(j)+"\n"
  if len(jadwal) > 0:
    return resp
  else:
    return "empty"

#catat waktu ke status
def timestamp():
  t = time.localtime()
  return time.asctime(t)

#baca sensor DHT
def readDHT(printing=False):
  try:
    newtemp = dht.temperature
    newhumid = dht.humidity
    if printing:
      print("Temp=", newtemp,"humid=", newhumid)
    with datalock: #.acquire():
      sensordata["temp"]=newtemp
      sensordata["humid"]=newhumid
      status["dht"]=1 #bisa angka atau juga bisa teks seperti "OK"
      status["time"]=timestamp()
  except RuntimeError as E:
    print("DHT Error:",E.args[0])
    with datalock:
      status["dht"]=0

#baca sensor lewat ADS
def readADS(printing=True):
  if i2cstatus==0:
    if printing:
      print("I2C not detected!")
    return
  new_ch0 = ch0.value
  new_ch1 = ch1.value
  if new_ch0>0: #nilainya wajar
    with datalock: #.acquire():
      sensordata["A0"]=new_ch0
      v = new_ch1*4.096/32767
      # awas math error, batasi v supaya 33000-v*10000 tidak negatif
      if v>3.2:
        print("LDR overvoltage:",v)
      elif v<=0:
        print("LDR voltage error, check connection! v =",v)
      try:
        v = min(3.2, v) # sekitar 2,7 juta lux - kalau sampai angka segini mungkin LDRnya korslet?
        lux = math.pow(((33000-v*10000)/(v*1043460)), (-1/0.548))
      except:
        print("Math error - set lux=0")
        lux=0
      lux = math.pow(((33000-v*10000)/(v*1043460)), (-1/0.548))
      #lux = exp(-ln(d)/0.548)+22.7)
      #lux = math.exp(-math.log(new_ch1)/0.548+22.7)
      sensordata["A1"]=lux
      status["time"]=timestamp()
      status["ADS"]=1
    if printing:
      print("A0=",new_ch0,"A1=",new_ch1,"v1=", v, "lux=",lux)
  else:
    with datalock: 
      status["ADS"]=0

#LED indikator, nomornya 0 dan 1
def setled(no=0,state=0):
  GPIO.output(pinLED[no], GPIO.HIGH if state>0 else GPIO.LOW)

def pwmout(percentage):
  ledpwm.duty_cycle = int(percentage*65535/100)

#fungsi-fungsi jadwal
def tambahjadwal(j):
  with jadwallock:
    jadwal.append(j)
  print("tambah jadwal", j)

def clearjadwal():
  with jadwallock:
    jadwal=[]
  print("clear jadwal")

def savejadwal(namafile):
  with jadwallock:
    f=open(namafile,'w')
    for j in jadwal:
      f.write(json.dumps(j)+"\n")
    f.close()
  print("save jadwal", namafile)

def bukajadwal(namafile):
  clearjadwal()
  f=open(namafile)
  lines=f.readlines()
  for l in lines:
    j=json.loads(l)
    tambahjadwal(j)
    print("buka jadwal", j)

def cekjadwal():
#cek waktu, cek semua jadwal ada yg cocok atau ga, klo ada yg cocok lakukan
  t=time.localtime()
  a=""
  s=time.strftime("%H%M",t)
  #waktu pergantian menit, aktifkan nyiram lagi -> set sudah_nyiram=False
  if t.tm_min != status["menit_terakhir"]:
    status["sudah_nyiram"]=False
  status["menit_terakhir"]=t.tm_min #update menit terakhir
  with jadwallock:
    for j in jadwal:
      if j["t"]==s:
        #lakukan action
        a = j["a"]
        print("actionnya", a)
        break
#list action: nyiram, led on, led off
  with datalock:
    if a =="nyiram" and status["sudah_nyiram"]==False :
      status["pump"]=1
      status["sudah_nyiram"]=True
    elif a=="led_on":
      status["led"]=1
    elif a=="led_off":
      status["led"]=0

def start_control_thread():
  while True:
    cekjadwal()
    print("ini lg cek jadwal")
    percentage = 0
    if status["led"]==1:
      #nyalain led sesuai dengan lux-nya :)
      if sensordata["A1"] < settings["lux_min"]: #di bawah 15.000 lx akan nyala 100% (65.535)
        percentage = 100
        pwmout(percentage)
        print("lux di bawah 15.000 > nyala maksimal")
      elif sensordata["A1"] < settings["lux_max"] : #di atas 15.000 s.d 30.000 akan menyala sesuai persentase
        percentage = (100/(settings["lux_min"]-settings["lux_man"])*sensordata["A1"]+100)
        pwmout(percentage)
        print("nyala lampu sesuai persentase")
      else: #30.000 ke atas, ga nyala
        percentage = 0
        pwmout(percentage)
        print("ga nyala, dah terang")
    elif status["led"]==0:
      pwmout(0)
      print("led mati")
    status["percentage_led"]=percentage
    #nyalain pompa
    if status["pump"]==1:
      status["pump"]=0
      if sensordata["A0"] > settings["basah"]:
        print("start pump")
        durasi_pump = ((sensordata["A0"]-settings["basah"])/(settings["kering"]-settings["basah"]))*settings["durasi_max_pump"] 
        setled(no=2,state=1)
        time.sleep(durasi_pump)
        setled(no=2,state=0)
        print("beres nyiram")
        pm = '?a=nyiram&val='+str(durasi_pump)
        print(url+pm)
        R=requests.get(url+pm)
        print('upload action>', R.ok)
    time.sleep(2)
        
#thread server
def start_server_thread():
  print("Server thread start")
  myapp.run(port=5000)
  print("Server thread end")

def start_measure_thread():
  print("Measure thread start")
  while True:
    setled(1,1)
    readADS(True) #True untuk print hasilnya ke terminal
    readDHT(True)
    time.sleep(0.05)
    setled(1,0)
    with datalock:
      t=settings["interval"]
    time.sleep(t-0.05)

def start_report_thread():
  while True:
    with datalock:
      pm = '?temp='+str(sensordata["temp"])+'&hum='+str(sensordata["humid"])+'&light='+str(sensordata["A1"])+'&sm='+str(sensordata["A0"])+'&led='+str(status["percentage_led"])
    print(url+pm)
    R=requests.get(url+pm)
    print('upload data>', R.ok)
    #time.sleep(settings["report_update"])
    t1=time.time()
    t2=t1
    with datalock:
      t=settings["report_update"]
    while t2-t1 < t:
      time.sleep(1)
      with datalock:
        t=settings["report_update"]
      t2=time.time()
      #time.sleep(1)

setled(0,1)
time.sleep(0.2)
setled(1,1)
time.sleep(0.2)
setled(0,0)
time.sleep(0.2)
setled(1,0)

if __name__== "__main__": #untuk apasih ini
  server_thread = threading.Thread(target=start_server_thread, daemon=True)
  server_thread.start()
  measure_thread = threading.Thread(target=start_measure_thread, daemon=True)
  measure_thread.start()
  report_thread = threading.Thread(target=start_report_thread, daemon=True)
  report_thread.start()
  control_thread = threading.Thread(target=start_control_thread, daemon=True)
  control_thread.start()
  #TODO: mengaktifkan output LED dan pompa
  #program utama menunggu di sini. Jika program utama selesai maka kedua thread daemon akan terminate

  while settings["running"]==1:
    time.sleep(1)

print("Stopping program...")
time.sleep(5)
print("Program end")
print("Bye :D")

