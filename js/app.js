document.addEventListener("DOMContentLoaded", async () => {

    const searchInput = document.querySelector(".search-box input");
    const menuGrid = document.querySelector(".menu-grid");

    let subjects = [];

    async function loadSubjects() {
        try {
            const response = await fetch("data/subjects.json");
            subjects = await response.json();
            displaySubjects(subjects);
        } catch (error) {
            console.log("Error loading subjects:", error);
        }
    }

    function displaySubjects(list) {

        menuGrid.innerHTML = "";

        list.forEach(subject => {

            menuGrid.innerHTML += `
                <div class="card">
                    <div class="icon">${subject.icon}</div>
                    <h3>${subject.name}</h3>
                </div>
            `;

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
