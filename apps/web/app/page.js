async function getBackendStatus(internalApiBaseUrl) {
  try {
    const response = await fetch(`${internalApiBaseUrl}/`, { cache: "no-store" });

    if (!response.ok) {
      return { reachable: false, status: response.status };
    }

    return {
      reachable: true,
      payload: await response.json(),
    };
  } catch (error) {
    return {
      reachable: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

export default async function HomePage() {
  const browserApiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const internalApiBaseUrl =
    process.env.INTERNAL_API_BASE_URL || "http://backend:8000";
  const backendStatus = await getBackendStatus(internalApiBaseUrl);

  return (
    <main
      style={{
        fontFamily: "sans-serif",
        padding: "2rem",
        display: "grid",
        gap: "1rem",
      }}
    >
      <h1>API Monitoring Platform</h1>
      <p>Local development frontend scaffold is running.</p>
      <p>Browser API URL: {browserApiBaseUrl}</p>
      <p>Internal API URL: {internalApiBaseUrl}</p>
      <pre
        style={{
          backgroundColor: "#111827",
          color: "#f9fafb",
          padding: "1rem",
          borderRadius: "0.5rem",
          overflowX: "auto",
        }}
      >
        {JSON.stringify(backendStatus, null, 2)}
      </pre>
    </main>
  );
}
