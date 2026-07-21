chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ANALYZE_TEXT") {
    fetch("http://127.0.0.1:5000/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: message.text,
        source_links: Array.isArray(message.source_links)
          ? message.source_links
          : []
      })
    })
      .then(response => {
        if (!response.ok) {
          throw new Error("Backend returned an error.");
        }
        return response.json();
      })
      .then(data => {
        sendResponse({
          success: true,
          data: data
        });
      })
      .catch(error => {
        console.error("Ethical Analyser fetch error:", error);
        sendResponse({
          success: false,
          error: "Backend API failed."
        });
      });

    return true;
  }
});