const BrandMark = ({ className = '' }) => (
  <svg
    aria-hidden="true"
    className={className}
    viewBox="0 0 36 36"
    fill="none"
  >
    <rect width="36" height="36" rx="11" fill="url(#requora-mark-bg)" />
    <path
      d="M11 26V10h8a5 5 0 0 1 0 10h-8m8 0 6 6"
      stroke="white"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2.5"
    />
    <defs>
      <linearGradient id="requora-mark-bg" x1="3" x2="34" y1="2" y2="35">
        <stop stopColor="#756BFF" />
        <stop offset="1" stopColor="#3478F6" />
      </linearGradient>
    </defs>
  </svg>
);

export default BrandMark;
