export const metadata = {
  title: "API Monitoring Platform",
  description: "Monitor APIs and websites",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
