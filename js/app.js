
const app = document.getElementById("app");

async function loadPage(page) {
    const response = await fetch(page);
    const html = await response.text();
    app.innerHTML = html;
}

loadPage("pages/home.html");
