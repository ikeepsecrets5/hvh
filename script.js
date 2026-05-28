const cards = document.querySelectorAll(".hero-card, .panel, .command-card");

cards.forEach(card => {
    card.addEventListener("mousemove", event => {
        const rect = card.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        card.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(255,255,255,.16), rgba(255,255,255,.07) 38%)`;
    });

    card.addEventListener("mouseleave", () => {
        card.style.background = "";
    });
});

async function refreshStatus() {
    const badge = document.querySelector(".pulse-badge");
    if (!badge) return;

    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        if (data.ok) badge.title = `${data.users} usuários monitorados`;
    } catch {}
}

refreshStatus();
setInterval(refreshStatus, 30000);
