// Add response interceptor for 401 errors
async function handleUnauthorized(response) {
    if (response.status === 401) {
        logout();
        return true;
    }
    return false;
}

let currentPage = 0;
const intPerPage = 50;

async function fetchUsers() {
    try {

        showLoader();

        const token = localStorage.getItem("x-access-token");
        const response = await fetch("/api/nubot/amadeus-air-ruler/get_all_users", {
            method: "GET",
            headers: {
                "x-access-token": token
            }
        });

        if (await handleUnauthorized(response)) return;

        const users = await response.json();
        const userFilter = document.getElementById("userFilter");
        
        users.forEach(user => {
            const option = document.createElement("option");
            option.value = user.intUserId;
            option.textContent = user.strUserName;
            userFilter.appendChild(option);
        });
    } catch (error) {
        console.error("Error fetching users:", error);
        showModal("Failed to load users.");

    } finally {
        hideLoader(); // Hide loader after API call completes
    }
}

// Add this function to handle filter clicks
function applyFilter() {
    currentPage = 0;  // Reset to first page
    loadLogs();
}

async function loadLogs() {
    try {

        showLoader();

        const token = localStorage.getItem("x-access-token");
        if (!token) {
            logout();
            return;
        }
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        const selectedUserid = document.getElementById('userFilter').value;

        // Check if end date is missing when searching
        if (startDate && !endDate) {
            showModal("Please select an end date.");
            hideLoader(); // Hide loader if validation fails
            return;
        }

        if (endDate && !startDate) {
            showModal("Please select an start date.");
            hideLoader(); // Hide loader if validation fails
            return;
        }

        if (startDate && endDate && new Date(startDate) > new Date(endDate)) {
            showModal("End date cannot be before start date");
            return;
        }

        const payload = {
            objPagination: {
                intPerPage: intPerPage,
                intPageOffset: currentPage,
                intTotalCount: 0 
            },
            objFilter: {
                strStartDate: startDate || null,
                strEndDate: endDate || null,
                intUserId: selectedUserid || null
            }
        };

        const response = await fetch("/api/nubot/amadeus-air-ruler/get_all_logs", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-access-token": token
            },
            body: JSON.stringify(payload)
        });

        // Check for 401 before processing response
        if (await handleUnauthorized(response)) return;

        const logs = await response.json();
        const logsTableBody = document.getElementById("logsTableBody");


        // Clear existing rows
        logsTableBody.innerHTML = '';
        
        document.getElementById("nextPage").disabled = logs.length < intPerPage;
        document.getElementById("prevPage").disabled = currentPage === 0;

        if (response.status === 400) {// Convert response to JSON
            showModal(logs.error);
            return;
        }
        

        logs.forEach(log => {
            let row = document.createElement("tr");
            row.innerHTML = `
                <td>${log.slNo}</td>
                <td>${log.strUserName}</td>
                <td>${log.strCompany || ''}</td>
                <td>${truncateText(log.strData)}</td>
                <td>${truncateText(log.strQuestion)}</td>
                <td>${truncateText(log.strResponse)}</td>
                <td>${formatDateTime(log.tim_created)}</td>
                <td>${log.strCost}</td>`;

            logsTableBody.appendChild(row);
        });

    } catch (error) {
        console.error("Error fetching logs:", error);
        if (error.message === "Unauthorized") {
            logout();
        } else {
            showModal("Failed to load logs. Please try again.");
        }
    } finally {
        hideLoader(); // Hide loader after API call completes
    }
};

function nextPage() {
    currentPage++;
    loadLogs();
}

function prevPage() {
    if (currentPage > 0) {
        currentPage--;
        loadLogs();
    }
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    const options = {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    };
    return date.toLocaleDateString('en-GB', options);
}

function truncateText(text, length = 100) {
    if (!text) return "";

    const parsedMarkdown = marked.parse(text);
    const shortText = marked.parse(text.substring(0, length) + "...");

    const id = "text_" + Math.random().toString(36).substring(2, 9);

    return `
        <div class="text-wrapper" id="${id}">
            <div class="short-text">${shortText}</div>
            <div class="full-text hidden">${parsedMarkdown}</div>
            <button class="read-more-btn" onclick="toggleText('${id}', this)">Read More</button>
        </div>
    `;
}

// Function to toggle between short and full text
function toggleText(id, button) {
    const wrapper = document.getElementById(id);
    const shortText = wrapper.querySelector(".short-text");
    const fullText = wrapper.querySelector(".full-text");

    if (fullText.classList.contains("hidden")) {
        shortText.style.display = "none";
        fullText.classList.remove("hidden");
        button.textContent = "Read Less";
    } else {
        shortText.style.display = "block";
        fullText.classList.add("hidden");
        button.textContent = "Read More";
    }
}


function showModal(message) {
    document.getElementById("modalMessage").textContent = message;
    document.getElementById("messageModal").style.display = "flex";
}


function closeModal() {
    document.getElementById("messageModal").style.display = "none";
    // Reset filters
    // document.getElementById("userFilter").value = ""; // Reset user selection
    // document.getElementById("startDate").value = "";  // Reset start date
    // document.getElementById("endDate").value = "";    // Reset end date;
}

function logout() {
    // Remove token from localStorage
    localStorage.removeItem("x-access-token");
    // Redirect to login page
    window.location.href = "/api/nubot/amadeus-air-ruler/login"; // Change this to your login route
}

function showLoader() {
    document.getElementById("loadingOverlay").style.display = "flex";
}

function hideLoader() {
    document.getElementById("loadingOverlay").style.display = "none";
}

// Initialize page
document.addEventListener("DOMContentLoaded", async () => {
    const token = localStorage.getItem("x-access-token");
    if (!token) {
        logout();
        return;
    }
    try {
        await fetchUsers();
        await loadLogs();
    } catch (error) {
        console.error("Initialization error:", error);
        logout();
    }
});

function backToDashboard() {
    window.location.href = "/api/nubot/amadeus-air-ruler/dashboard"; // Adjust this URL if your dashboard route is different.
}