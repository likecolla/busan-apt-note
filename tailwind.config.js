// 공부노트·특별호 "한눈에 보기" 대시보드용 Tailwind 설정.
// busan_note/dashboard.py 의 클래스만 모아 busan_note/dashboard.css 로 빌드한다(페이지에 그대로 넣음).
// 빌드: npx tailwindcss@3.4.16 -c tailwind.config.js -o busan_note/dashboard.css --minify
module.exports = {
  content: ["./busan_note/dashboard.py"],
  prefix: "tw-",
  corePlugins: { preflight: false },  // 기존 페이지 스타일을 건드리지 않도록 초기화 CSS는 끔
};
