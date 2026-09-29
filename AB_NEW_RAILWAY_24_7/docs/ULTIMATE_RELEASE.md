# AB NEW ULTIMATE
هذه النسخة مبنية فوق المحرك الكامل، وليست Skeleton.

## Live
- Socket.IO للرسائل والدعوات وحالات الألعاب.
- polling fallback عند ضعف WebSocket.
- الرد الآلي يُحفظ كرسالة عامة ويُبث للقروب.

## Economy / Store
- منتجات يرفعها الـOwner: avatar / frame / title / badge-crown / effect.
- شراء بالنقاط، ملكية دائمة، وتفعيل عنصر واحد من كل نوع.
- اللقب المفعّل يظهر مع الاسم.
- الصورة/الإطار/التاج المفعّل يظهر في الملف الشخصي.
- طلب شراء نقاط وموافقة/رفض من الـOwner.
- إضافة/خصم نقاط يدوياً من لوحة الإدارة.

## Games
- X/O server-authoritative.
- Domino 2/3 players: hidden hands, chain ends, draw/pass/block result.
- Backgammon: dice, doubles, bar priority, hits, blocked points, bearing-off checks.
- Quiz: configurable timer; correct score decreases from 100 with elapsed time; wrong/late = 0.

## Visual/PWA
- Mobile-first dark neon UI.
- local textures/audio/theme pack.
- manifest + service worker.
