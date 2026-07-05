"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export default function LandingPage() {
  const router = useRouter();
  const dedicationRef = useRef<HTMLDivElement>(null);

  // Scroll reveal للقسم الإهداء
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("opacity-100", "translate-y-0");
            entry.target.classList.remove("opacity-0", "translate-y-8");
          }
        });
      },
      { threshold: 0.2 }
    );
    const elements = document.querySelectorAll(".reveal");
    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <main
      className="min-h-screen bg-[#FAFAF7] text-[#1C1C1C]"
      dir="rtl"
      style={{ fontFamily: "'Amiri', 'Georgia', serif" }}
    >
      {/* ── Google Fonts ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&display=swap');

        .reveal {
          opacity: 1;
          transform: translateY(2rem);
          transition: opacity 0.7s ease, transform 0.7s ease;
        }
        .gold { color: #B8860B; }
        .gold-border { border-color: #B8860B; }
        .gold-bg { background-color: #B8860B; }
        .gold-bg-light { background-color: #B8860B18; }

        /* زخرفة الإهداء */
        .dedication-frame {
          position: relative;
          border: 1px solid #B8860B44;
          background: linear-gradient(135deg, #FFFEF8 0%, #FFF9E6 100%);
        }
        .dedication-frame::before,
        .dedication-frame::after {
          // content: '✦';
          position: absolute;
          color: #B8860B88;
          font-size: 1.2rem;
        }
        .dedication-frame::before { top: 1rem; right: 1.5rem; }
        .dedication-frame::after  { bottom: 1rem; left: 1.5rem; }

        .ornament {
          display: inline-block;
          color: #B8860B;
          letter-spacing: 0.5rem;
          opacity: 0.6;
          font-size: 0.75rem;
        }
      `}</style>

      {/* ── Header ── */}
      <header className="border-b border-[#E8E4DB] bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold tracking-tight">
              تبيان
            </span>
            <span className="gold text-2xl font-bold">/ Tebayn</span>
          </div>
          <button
            onClick={() => router.push("/")}
            className="gold-bg text-white px-5 py-2 rounded-lg text-sm font-medium
                       hover:opacity-90 active:opacity-80 transition-opacity"
          >
            ابدأ الآن
          </button>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16 text-center">
        <span className="ornament">❧ ❧ ❧</span>

        <h1 className="text-5xl md:text-6xl font-bold leading-tight mt-6 mb-6">
          اقرأ بعمق،
          <br />
          <span className="gold">فهِم بوضوح</span>
        </h1>

        <p className="text-xl text-[#555] leading-relaxed max-w-2xl mx-auto mb-10">
          تبيان يحوّل ملفاتك الأكاديمية إلى مراجعة يدوية ذكية —
          خطوط تحت الجمل المهمة، دوائر حول المصطلحات،
          وملاحظات هامشية عربية بأسلوب يحاكي يد المراجع الحقيقي.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => router.push("/")}
            className="gold-bg text-white px-8 py-3.5 rounded-xl text-base font-medium
                       hover:opacity-90 transition-opacity shadow-sm"
          >
            جرّب مجاناً — ارفع ملف PDF
          </button>
          <a
            href="#how"
            className="px-8 py-3.5 rounded-xl text-base border border-[#D4C5A0]
                       text-[#555] hover:bg-[#F5F0E8] transition-colors"
          >
            كيف يعمل؟
          </a>
        </div>

        {/* مثال بصري مبسط */}
        <div className="mt-16 relative max-w-2xl mx-auto">
          <div className="bg-white border border-[#E8E4DB] rounded-2xl shadow-lg p-8 text-right">
            <p className="text-xs text-[#999] mb-4 text-center">مثال على مخرجات تبيان</p>
            <div className="space-y-4">
              {/* جملة مسطّرة */}
              <div className="relative">
                <p className="text-sm leading-7 text-[#333]">
                  <span
                    className="relative inline"
                    style={{
                      textDecoration: "underline wavy #B8860B",
                      textUnderlineOffset: "4px",
                    }}
                  >
                    تُعدّ اللغويات الحسابية من أبرز التخصصات الناشئة في القرن الحادي والعشرين،
                  </span>
                  {" "}إذ تجمع بين علم اللغة والذكاء الاصطناعي.
                </p>
                {/* ملاحظة هامشية */}
                <span
                  className="absolute -right-28 top-0 text-xs gold opacity-80 hidden md:block"
                  style={{ fontStyle: "italic", writingMode: "horizontal-tb" }}
                >
                  ← تعريف محوري
                </span>
              </div>
              {/* كلمة بدائرة */}
              <p className="text-sm leading-7 text-[#333]">
                يعتمد هذا المجال على نماذج{" "}
                <span
                  className="inline-block px-1 rounded-full border-2 gold-border"
                  style={{ borderRadius: "50%", padding: "0 6px" }}
                >
                  ماركوف
                </span>
                {" "}وشبكات عصبية عميقة لمعالجة اللغة الطبيعية.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── كيف يعمل ── */}
      <section id="how" className="bg-white border-y border-[#E8E4DB] py-20">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-14 reveal">
            <span className="ornament">❧ ❧ ❧</span>
            <h2 className="text-3xl font-bold mt-4 mb-3">كيف يعمل تبيان؟</h2>
            <p className="text-[#777] max-w-md mx-auto">
              ثلاث خطوات فقط من الملف الخام إلى المراجعة الذكية
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                num: "١",
                title: "ارفع ملفك",
                desc: "اسحب أي ملف PDF أكاديمي — بحوث، كتب، محاضرات، مقالات. الحجم الأقصى 20MB.",
                icon: "📄",
              },
              {
                num: "٢",
                title: "التحليل الذكي",
                desc: "يقرأ الذكاء الاصطناعي المحتوى ويحدد الجمل الجوهرية والمصطلحات التقنية الأبرز.",
                icon: "🧠",
              },
              {
                num: "٣",
                title: "مراجعة بخط اليد",
                desc: "يرسم خطوطاً متعرجة، دوائر، وملاحظات هامشية عربية — ثم يسلّمك الملف جاهزاً.",
                icon: "✍️",
              },
            ].map(({ num, title, desc, icon }) => (
              <div key={num} className="reveal text-center">
                <div className="w-14 h-14 gold-bg-light rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl">
                  {icon}
                </div>
                <div className="gold text-4xl font-bold mb-3 opacity-30">{num}</div>
                <h3 className="text-lg font-bold mb-2">{title}</h3>
                <p className="text-[#777] text-sm leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── المميزات ── */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <div className="text-center mb-14 reveal">
          <span className="ornament">❧ ❧ ❧</span>
          <h2 className="text-3xl font-bold mt-4 mb-3">لماذا تبيان؟</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[
            {
              title: "مراجعة تحاكي خط اليد",
              desc: "لا خطوط آلية باردة — منحنيات بيزيه تعطي شعور القلم الحقيقي فوق الورق.",
            },
            {
              title: "ملاحظات هامشية عربية",
              desc: "تعليقات قصيرة بالعربية في هوامش الصفحة، مرتبطة بسياقها بدقة.",
            },
            {
              title: "يفهم المحتوى الأكاديمي",
              desc: "مدرّب على التمييز بين التعريفات والنتائج والأفكار المحورية.",
            },
            {
              title: "مجاني وبدون تسجيل",
              desc: "ارفع ملفك مباشرة ونزّل النتيجة — لا حسابات، لا بيانات شخصية.",
            },
          ].map(({ title, desc }) => (
            <div
              key={title}
              className="reveal flex gap-4 p-6 rounded-2xl border border-[#E8E4DB]
                         bg-white hover:border-[#B8860B44] transition-colors"
            >
              <div className="gold text-xl mt-0.5 shrink-0">✦</div>
              <div>
                <h3 className="font-bold mb-1">{title}</h3>
                <p className="text-[#777] text-sm leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── قسم الإهداء ── */}
      <section className="max-w-3xl mx-auto px-6 pb-20" ref={dedicationRef}>
        <div className="reveal dedication-frame rounded-2xl px-10 py-10 text-center">
          <span className="ornament">﴾ ﴿</span>

          <blockquote className="mt-6 mb-6">
            <p className="text-2xl leading-loose font-bold text-[#2C2C2C]">
              إِذَا مَاتَ الإِنسَانُ انْقَطَعَ عَنْهُ عَمَلُهُ إِلَّا مِنْ ثَلَاثَةٍ:
              <br />
              <span className="gold">صَدَقَةٍ جَارِيَةٍ</span>، أَوْ عِلْمٍ يُنْتَفَعُ بِهِ،
              <br />
              أَوْ وَلَدٍ صَالِحٍ يَدْعُو لَهُ
            </p>
            <footer className="text-sm text-[#999] mt-3">— صحيح مسلم</footer>
          </blockquote>

          <div className="w-24 h-px bg-[#B8860B44] mx-auto my-6" />

          <p className="text-lg leading-8 text-[#555]">
            هذا المشروع صدقة جارية
            <br />
            لروح والدنا الكريم
          </p>

          <p className="text-2xl font-bold text-[#2C2C2C] mt-3 mb-1">
            كمال الدين
          </p>

          <p className="text-sm text-[#999]">
            رحمه الله وأسكنه فسيح جناته
          </p>

          <p className="text-sm text-[#AAA] mt-4">
            والأسرة الكريمة 🌹
          </p>

          <span className="ornament mt-6 block">﴾ ﴿</span>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="bg-[#1C1C1C] text-white py-16 text-center">
        <div className="max-w-xl mx-auto px-6">
          <span className="ornament text-white/30">❧ ❧ ❧</span>
          <h2 className="text-3xl font-bold mt-4 mb-4">
            جاهز لتجربة تبيان؟
          </h2>
          <p className="text-white/60 mb-8 leading-relaxed">
            ارفع ملفك الأكاديمي الآن وشاهد الفرق
          </p>
          <button
            onClick={() => router.push("/")}
            className="gold-bg px-10 py-4 rounded-xl text-base font-bold
                       hover:opacity-90 transition-opacity"
          >
            ابدأ مجاناً الآن
          </button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-[#E8E4DB] bg-white py-8 text-center">
        <p className="text-[#AAA] text-sm">
          تبيان — جميع الحقوق محفوظة · مشروع مفتوح المصدر
        </p>
        <p className="text-[#CCC] text-xs mt-2">
          🌹 في ذكرى والدنا كمال الدين — رحمة الله عليه
        </p>
      </footer>
    </main>
  );
}
