console.log("SSC Smart Study Started");

async function loadSubjects() {
    try {
        const response = await fetch("data/subjects.json");
        const subjects = await response.json();

        console.log(subjects);
    } catch (error) {
        console.error(error);
    }
}

loadSubjects();
