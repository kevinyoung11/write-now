export function WordflowPage() {
  return (
    <iframe
      src="/wordflow/index.html"
      title="Wordflow editor"
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
      referrerPolicy="no-referrer"
      style={{
        border: 0,
        display: "block",
        minHeight: "100vh",
        width: "100%",
      }}
    />
  );
}
