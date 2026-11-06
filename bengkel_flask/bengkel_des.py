import numpy as np

# ===== Fungsi bantu: menjadwalkan kejadian ke event calendar =====
def jadwalkan(st, waktu, tipe, id_mobil):
    st["calendar"].append([waktu, tipe, id_mobil])
    st["calendar"].sort()              # calendar harus selalu terurut menurut waktu

# ===== Resepsionis: layani antrian terdepan jika sedang bebas =====
def layani_resepsionis(st):
    if st["resepsionis"] == "IDLE" and st["antrian_resp"]:
        id_mobil, tugas = st["antrian_resp"].pop(0)     # FIFO
        st["resepsionis"] = "BUSY"
        st["total_tunggu_resp"] += st["clock"] - st["masuk_resp"][(id_mobil, tugas)]
        if tugas == "DAFTAR":
            durasi, tipe = st["t_daftar"], "SELESAI_DAFTAR"
        else:
            durasi, tipe = st["t_bayar"], "SELESAI_BAYAR"
        st["waktu_sibuk_resp"] += durasi
        jadwalkan(st, st["clock"] + durasi, tipe, id_mobil)

# ===== Montir: ambil mobil dari ruang tunggu selama ada montir bebas =====
def mulai_perbaikan(st):
    while st["montir_bebas"] > 0 and st["antrian_montir"]:
        id_mobil = st["antrian_montir"].pop(0)          # FIFO
        st["montir_bebas"] -= 1
        tunggu = st["clock"] - st["masuk_antrian_montir"][id_mobil]
        st["total_tunggu_montir"] += tunggu
        st["max_tunggu_montir"] = max(st["max_tunggu_montir"], tunggu)
        st["mobil_diperbaiki"] += 1
        durasi = np.random.uniform(st["rep_min"], st["rep_max"])
        st["waktu_sibuk_montir"] += durasi
        jadwalkan(st, st["clock"] + durasi, "SELESAI_PERBAIKAN", id_mobil)

# ===== Event handler: satu fungsi untuk satu jenis kejadian =====
def handle_arrival(st, id_mobil):
    st["waktu_datang"][id_mobil] = st["clock"]
    # jadwalkan kedatangan berikutnya (hanya jika masih jam buka)
    berikut = st["clock"] + np.random.exponential(st["mean_iat"])
    if berikut <= st["jam_buka"]:
        jadwalkan(st, berikut, "ARRIVAL", id_mobil + 1)
    # mobil mendaftar di resepsionis
    st["antrian_resp"].append((id_mobil, "DAFTAR"))
    st["masuk_resp"][(id_mobil, "DAFTAR")] = st["clock"]
    ket = "Langsung didaftar" if st["resepsionis"] == "IDLE" else "Antri di resepsionis"
    layani_resepsionis(st)
    return ket

def handle_selesai_daftar(st, id_mobil):
    st["resepsionis"] = "IDLE"
    ket = "Langsung diperbaiki" if st["montir_bebas"] > 0 else "Menunggu montir"
    st["antrian_montir"].append(id_mobil)
    st["masuk_antrian_montir"][id_mobil] = st["clock"]
    mulai_perbaikan(st)
    layani_resepsionis(st)
    return ket

def handle_selesai_perbaikan(st, id_mobil):
    st["montir_bebas"] += 1
    st["antrian_resp"].append((id_mobil, "BAYAR"))
    st["masuk_resp"][(id_mobil, "BAYAR")] = st["clock"]
    mulai_perbaikan(st)
    layani_resepsionis(st)
    return "Menuju pembayaran"

def handle_selesai_bayar(st, id_mobil):
    st["resepsionis"] = "IDLE"
    st["mobil_selesai"] += 1
    st["total_waktu_sistem"] += st["clock"] - st["waktu_datang"][id_mobil]
    layani_resepsionis(st)
    return "Mobil keluar"

# ===== Program utama: inisialisasi, main loop, statistik akhir =====
# tampilkan_log : cetak log ke layar (dipakai di notebook)
# simpan_log    : simpan log dan timeline ke dalam hasil (dipakai di web Flask)
def simulasi_bengkel(seed=42, jam_buka=480, mean_iat=30, t_daftar=5, t_bayar=5,
                     rep_min=30, rep_max=60, jumlah_montir=2,
                     tampilkan_log=False, simpan_log=False):
    np.random.seed(seed)

    # 1. Inisialisasi: clock, state, antrian, event calendar, statistik
    st = {
        "clock": 0.0, "calendar": [], "jam_buka": jam_buka, "mean_iat": mean_iat,
        "t_daftar": t_daftar, "t_bayar": t_bayar, "rep_min": rep_min, "rep_max": rep_max,
        "montir_bebas": jumlah_montir, "resepsionis": "IDLE",
        "antrian_resp": [], "antrian_montir": [],
        "masuk_resp": {}, "masuk_antrian_montir": {}, "waktu_datang": {},
        "total_tunggu_resp": 0.0, "total_tunggu_montir": 0.0, "max_tunggu_montir": 0.0,
        "waktu_sibuk_montir": 0.0, "waktu_sibuk_resp": 0.0, "total_waktu_sistem": 0.0,
        "mobil_diperbaiki": 0, "mobil_selesai": 0,
    }
    # jadwalkan kedatangan pertama
    jadwalkan(st, np.random.exponential(mean_iat), "ARRIVAL", 1)

    log, timeline = [], [(0.0, 0)]
    if tampilkan_log:
        print(f"{'Clock':<9}{'Event':<19}{'Mobil':<7}{'Antri Resp':<12}{'Antri Montir':<14}{'Montir Bebas':<14}{'Resepsionis':<13}Keterangan")
        print("-" * 105)

    handler = {"ARRIVAL": handle_arrival, "SELESAI_DAFTAR": handle_selesai_daftar,
               "SELESAI_PERBAIKAN": handle_selesai_perbaikan, "SELESAI_BAYAR": handle_selesai_bayar}

    # 2. Main simulation loop: jalan selama event calendar tidak kosong
    while st["calendar"]:
        waktu, tipe, id_mobil = st["calendar"].pop(0)    # ambil kejadian paling awal
        st["clock"] = waktu                              # jam melompat ke waktu kejadian
        ket = handler[tipe](st, id_mobil)                # panggil handler yang sesuai
        if tampilkan_log:
            print(f"{waktu:<9.2f}{tipe:<19}{id_mobil:<7}{len(st['antrian_resp']):<12}{len(st['antrian_montir']):<14}{st['montir_bebas']:<14}{st['resepsionis']:<13}{ket}")
        if simpan_log:
            log.append({"clock": round(waktu, 2), "event": tipe, "mobil": id_mobil,
                        "antri_resp": len(st["antrian_resp"]), "antri_montir": len(st["antrian_montir"]),
                        "montir_bebas": st["montir_bebas"], "resepsionis": st["resepsionis"], "ket": ket})
            timeline.append((waktu, len(st["antrian_montir"])))

    # 3. Statistik akhir
    akhir = st["clock"]
    hasil = {
        "mobil_datang": len(st["waktu_datang"]), "mobil_selesai": st["mobil_selesai"], "waktu_akhir": akhir,
        "rata_tunggu_montir": st["total_tunggu_montir"] / max(st["mobil_diperbaiki"], 1),
        "maks_tunggu_montir": st["max_tunggu_montir"],
        "rata_tunggu_resp": st["total_tunggu_resp"] / max(2 * st["mobil_selesai"], 1),
        "util_montir": st["waktu_sibuk_montir"] / (jumlah_montir * akhir),
        "util_resp": st["waktu_sibuk_resp"] / akhir,
        "rata_waktu_sistem": st["total_waktu_sistem"] / max(st["mobil_selesai"], 1),
    }
    if tampilkan_log:
        print("\n=== HASIL SIMULASI ===")
        print(f"Mobil datang                   : {hasil['mobil_datang']}")
        print(f"Mobil selesai                  : {hasil['mobil_selesai']}")
        print(f"Waktu simulasi berakhir        : {akhir:.2f} menit")
        print(f"Rata-rata tunggu montir        : {hasil['rata_tunggu_montir']:.2f} menit")
        print(f"Waktu tunggu montir maksimum   : {hasil['maks_tunggu_montir']:.2f} menit")
        print(f"Rata-rata tunggu resepsionis   : {hasil['rata_tunggu_resp']:.2f} menit")
        print(f"Utilisasi montir (rata-rata)   : {hasil['util_montir']*100:.1f} %")
        print(f"Utilisasi resepsionis          : {hasil['util_resp']*100:.1f} %")
        print(f"Rata-rata waktu di bengkel     : {hasil['rata_waktu_sistem']:.2f} menit")
    if simpan_log:
        hasil["log"], hasil["timeline"] = log, timeline
    return hasil

if __name__ == "__main__":
    simulasi_bengkel(seed=42, tampilkan_log=True)
