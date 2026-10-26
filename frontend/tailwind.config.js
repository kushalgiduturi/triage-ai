/**
 * TriageAI design tokens: spatial UI in white and sky blue.
 * Three elevation levels (0 base, 1 content, 2 focus). Red is reserved for Critical urgency.
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      white: "#FFFFFF",
      ink: "#0F172A", // body text
      muted: "#64748B", // secondary text
      line: "#E2E8F0", // hairlines and dividers
      mist: "#F0F9FF", // selected rows, subtle fills
      sky: {
        DEFAULT: "#0EA5E9", // primary accent: dots, bars, focus ring, active marker
        deep: "#0284C7", // hover / pressed accent
        // Text-safe sky shades (WCAG AA on white): used for sky-blue text and button fills.
        text: "#0369A1", // 5.9:1
        strong: "#075985", // 7.6:1
        night: "#0C4A6E", // 9.5:1
      },
      critical: "#DC2626", // 4.8:1, the only non-blue colour; Critical urgency only
      scrim: "rgba(255, 255, 255, 0.75)", // soft white scrim behind confirmation dialogs
    },
    fontFamily: { sans: ["Inter", "SF Pro Text", "system-ui", "sans-serif"] },
    extend: {
      fontSize: {
        title: ["28px", { lineHeight: "34px", letterSpacing: "-0.02em", fontWeight: "600" }],
        section: ["12px", { lineHeight: "16px", letterSpacing: "0.06em" }],
      },
      // l1 / l2: the two surface levels. pill: nav dock, buttons, dots. control: text inputs.
      borderRadius: { l1: "28px", l2: "24px", pill: "9999px", control: "12px" },
      boxShadow: {
        l1: "0 20px 60px rgba(14,165,233,0.10)",
        l2: "0 12px 40px rgba(2,132,199,0.16)",
      },
      backdropBlur: { glass: "24px" },
      maxWidth: { content: "1280px" },
    },
  },
  plugins: [],
};
