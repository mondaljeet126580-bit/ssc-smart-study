document.addEventListener("DOMContentLoaded", async () => {

    const searchInput = document.querySelector(".search-box input");
    const menuGrid = document.querySelector(".menu-grid");

    let subjects = [];

    async function loadSubjects() {
        const response = await fetch("data/subjects.json");
        subjects = await response.json();
        displaySubjects(subjects);
    }

    function displaySubjects(list) {

        menuGrid.innerHTML = "";

        list.forEach(subject => {

            const card = document.createElement("div");
            card.className = "card";

            card.innerHTML = `
                <div class="icon">${subject.icon}</div>
                <h3>${subject.name}</h3>
            `;

            card.onclick = () => {

                window.location.href =
                    "pages/subject.html?name=" +
                    encodeURIComponent(subject.name);

            };

            menuGrid.appendChild(card);

        });

    }

    searchInput.addEventListener("input", function () {

        const keyword = this.value.toLowerCase();

        const filtered = subjects.filter(subject =>
            subject.name.toLowerCase().includes(keyword)
        );

        displaySubjects(filtered);

    });

    loadSubjects();

});
