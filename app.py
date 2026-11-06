import io
import base64
import threading

import numpy as np
import matplotlib
matplotlib.use("Agg")                      # backend tanpa layar, untuk server
import matplotlib.pyplot as plt
from flask import Flask, render_template, request

from bengkel_des import simulasi_bengkel

app = Flask(__name__)
kunci = threading.Lock()                   # np.random.seed bersifat global, jadi simulasi dijalankan satu per satu

# Nilai awal form dan batas yang diperbolehkan: (bawaan, minimum, maksimum, tipe)
PARAMETER = {
    "seed":          (42,   0,   2**31 - 1, int),
    "jam_buka":      (480,  60,  1440,      float),
    "mean_iat":      (30,   1,   240,       float),
    "t_daftar":      (5,    0.5, 60,        float),
    "t_bayar":       (5,    0.5, 60,        float),
    "rep_min":       (30,   1,   600,       float),
    "rep_max":       (60,   1,   600,       float),
    "jumlah_montir": (2,    1,   5,         int),
    "replikasi":     (1,    1,   1000,      int),
}


def baca_form(form):
    """Baca dan validasi input. Mengembalikan (nilai, daftar_error)."""
    nilai, error = {}, []
    for nama, (bawaan, minimum, maksimum, tipe) in PARAMETER.items():
        mentah = form.get(nama, "").strip()
        if mentah == "":
            nilai[nama] = bawaan
            continue
        try:
            angka = tipe(float(mentah)) if tipe is int else float(mentah)
        except ValueError:
            error.append(f"{nama} harus berupa angka.")
            nilai[nama] = bawaan
            continue
        if not (minimum <= angka <= maksimum):
            error.append(f"{nama} harus antara {minimum} dan {maksimum}.")
            nilai[nama] = bawaan
        else:
            nilai[nama] = angka
    if nilai["rep_min"] > nilai["rep_max"]:
        error.append("rep_min tidak boleh lebih besar dari rep_max.")
    return nilai, error


def grafik_antrian(timeline, jam_buka):
    """Buat grafik panjang antrian montir terhadap waktu, hasilnya string base64."""
    waktu = [t for t, _ in timeline]
    panjang = [p for _, p in timeline]
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.step(waktu, panjang, where="post", color="tab:blue")
    ax.axvline(jam_buka, color="red", linestyle="--", label="Bengkel tutup")
    ax.set_xlabel("Waktu simulasi (menit)")
    ax.set_ylabel("Mobil di ruang tunggu")
    ax.set_title("Panjang antrian ruang tunggu montir")
    ax.legend()
    ax.grid(True, alpha=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


@app.route("/", methods=["GET", "POST"])
def index():
    nilai = {nama: spek[0] for nama, spek in PARAMETER.items()}
    error, hasil, rata2, grafik = [], None, None, None

    if request.method == "POST":
        nilai, error = baca_form(request.form)
        if not error:
            parameter_sim = {k: nilai[k] for k in
                             ["jam_buka", "mean_iat", "t_daftar", "t_bayar",
                              "rep_min", "rep_max", "jumlah_montir"]}
            with kunci:
                # satu kali run dengan log lengkap
                hasil = simulasi_bengkel(seed=int(nilai["seed"]), simpan_log=True, **parameter_sim)
                # replikasi untuk rata-rata yang lebih stabil (seed 1..N)
                if nilai["replikasi"] > 1:
                    semua = [simulasi_bengkel(seed=s, **parameter_sim)
                             for s in range(1, int(nilai["replikasi"]) + 1)]
                    kunci_rata = ["mobil_datang", "rata_tunggu_montir", "util_montir",
                                  "util_resp", "rata_waktu_sistem"]
                    rata2 = {k: float(np.mean([x[k] for x in semua])) for k in kunci_rata}
            grafik = grafik_antrian(hasil["timeline"], nilai["jam_buka"])

    return render_template("index.html", nilai=nilai, error=error,
                           hasil=hasil, rata2=rata2, grafik=grafik)


if __name__ == "__main__":
    app.run(debug=True)                    # debug=True hanya untuk pengembangan lokal
