# kgreenhouse
Cara menjalankan:
python3 app.py

### Web user interface:
`/`

Menampilkan data real time.

`/data`

Menampilkan data terakhir dalam bentuk JSON. (tidak update otomatis)

`/settings`

Menampilkan variabel-variabel settings.

`/settings?ru=ss`

Mengubah interval report update atau mengirim data ke Google apps script, dalam detik.

`/settings?restart=y`

Terminate server. Untuk menjalankannya lagi bisa lewat Dataplicity.

`/settings?testpump=ss`

Menyalakan pompa selama ss detik.

`/settings?testled=ppp`

Menyalakan LED grow light dengan PWM duty cycle sebesar ppp persen.

`/settings?autoled=x`

Mengaktifkan pengaturan terang LED secara otomatis sesuai nilai LDR di luar jadwal. x=1 aktif, x=0 mati.

`/status`

Menampilkan status.

`/jadwal`

Menampilkan jadwal. Kalau kosong maka akan muncul "empty".

`/jadwal?t=hhmm&a=action`

Menambahkan entri jadwal pada jam hhmm dengan pilihan action: nyiram, led_on, led_off

`/jadwal?load=namafile`

Membuka jadwal yang tersimpan dalam file text. Jawabannya hanya "OK".

`/jadwal?save=namafile`

Menyimpan jadwal menjadi file text. Jawabannya hanya "OK".
