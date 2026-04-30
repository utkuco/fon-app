import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Çerez Politikası",
  description:
    "FonRapor.com çerez politikası — hangi çerezler kullanılır, nasıl yönetilir.",
};

export default function CerezPolitikasiPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold text-neutral-900 mb-6">Çerez Politikası</h1>

      <div className="space-y-6 text-sm text-neutral-700 leading-relaxed">
        <p>
          FonRapor.com olarak, site deneyiminizi iyileştirmek ve hizmetlerimizi sunmak
          amacıyla çerezler kullanmaktayız. Bu politika, çerezlerin ne olduğunu, hangi
          amaçlarla kullandığımızı ve nasıl yönetebileceğinizi açıklamaktadır.
        </p>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">Çerez Nedir?</h2>
        <p>
          Çerezler, bir web sitesini ziyaret ettiğinizde tarayıcınız aracılığıyla cihazınıza
          yerleştirilen küçük metin dosyalarıdır. Çerezler, site tercihlerinizi hatırlamak,
          güvenli oturumlar kurmak ve site trafiğini analiz etmek için yaygın olarak
          kullanılmaktadır.
        </p>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">
          Kullandığımız Çerez Kategorileri
        </h2>

        <div className="space-y-4">
          <div className="border border-neutral-200 rounded-lg p-4">
            <h3 className="font-semibold text-neutral-900 mb-1">
              Zorunlu Çerezler (Kesinlikle Gerekli)
            </h3>
            <p className="text-xs text-neutral-500 mb-2">
              Bu çerezler site çalışması için zorunludur. Açık rızanız olmadan
              kullanımları mümkündür.
            </p>
            <ul className="list-disc list-inside text-xs space-y-1 text-neutral-600">
              <li>
                <strong>Oturum çerezleri</strong> — Sunucu-istemci iletişimini yönetir,
                site performansını optimize eder
              </li>
              <li>
                <strong>Güvenlik çerezleri</strong> — Site güvenliğini sağlamak için
                kullanılır
              </li>
            </ul>
          </div>

          <div className="border border-neutral-200 rounded-lg p-4">
            <h3 className="font-semibold text-neutral-900 mb-1">
              Performans ve Analitik Çerezler
            </h3>
            <p className="text-xs text-neutral-500 mb-2">
              Site trafiğini ve kullanımını anlamamıza yardımcı olur.
            </p>
            <ul className="list-disc list-inside text-xs space-y-1 text-neutral-600">
              <li>
                <strong>Google Analytics</strong> — Ziyaretçi sayısı, sayfa görüntülemeleri,
                trafik kaynakları gibi anonim istatistikler toplar. IP adresiniz
                anonimleştirilir.
                <br />
                <span className="text-neutral-400">
                  Sağlayıcı: Google LLC, ABD ·{" "}
                  <a
                    href="https://policies.google.com/technologies/partner-sites"
                    className="underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Gizlilik Politikası
                  </a>
                </span>
              </li>
            </ul>
          </div>

          <div className="border border-neutral-200 rounded-lg p-4">
            <h3 className="font-semibold text-neutral-900 mb-1">
              Üçüncü Taraf İçerik Çerezleri
            </h3>
            <p className="text-xs text-neutral-500 mb-2">
              YouTube videoları veya haritalar gibi gömülü içeriklerden kaynaklanır.
            </p>
            <ul className="list-disc list-inside text-xs space-y-1 text-neutral-600">
              <li>
                <strong>YouTube embed</strong> — Gömülü fon tanıtım videoları için.
                <br />
                <span className="text-neutral-400">
                  Sağlayıcı: Google LLC, ABD ·{" "}
                  <a
                    href="https://policies.google.com/privacy"
                    className="underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Gizlilik Politikası
                  </a>
                </span>
              </li>
            </ul>
          </div>
        </div>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">
          Çerezleri Nasıl Yönetebilirsiniz?
        </h2>
        <p>
          Tarayıcı ayarlarınızdan çerezleri devre dışı bırakabilir veya silebilirsiniz. Ancak
          bu durumda site bazı özelliklerinin düzgün çalışmayabileceğini lütfen unutmayın.
        </p>

        <div className="bg-neutral-50 rounded-lg p-4 space-y-2">
          <p className="text-xs font-semibold text-neutral-700">Popüler tarayıcılar için:</p>
          <ul className="text-xs space-y-1 text-neutral-600">
            <li>
              <strong>Chrome:</strong> Ayarlar → Gizlilik ve güvenlik → Çerezler
            </li>
            <li>
              <strong>Firefox:</strong> Ayarlar → Gizlilik ve Güvenlik → Çerezler
            </li>
            <li>
              <strong>Safari:</strong> Tercihler → Gizlilik → Çerezler
            </li>
            <li>
              <strong>Edge:</strong> Ayarlar → Çerezler ve site izinleri
            </li>
          </ul>
        </div>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">
          Politika Değişiklikleri
        </h2>
        <p>
          Bu çerez politikası zaman zaman güncellenebilir. Değişiklikler bu sayfada
          yayınlanacaktır.
        </p>

        <div className="border-t border-neutral-200 pt-4 mt-6 text-xs text-neutral-500">
          <p>
            Son güncelleme:{" "}
            {new Date().toLocaleDateString("tr-TR", {
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </p>
          <p className="mt-1">
            Sorularınız için:{" "}
            <a href="mailto:bilgi@fonrapor.com" className="text-blue-600 underline">
              bilgi@fonrapor.com
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}
