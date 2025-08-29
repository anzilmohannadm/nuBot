// Add response interceptor for 401 errors
async function handleUnauthorized(response) {
    if (response.status === 401) {
        logout();
        return true;
    }
    return false;
}

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
        if (error.message === "Unauthorized") {
            logout();
        } else {
            showModal("Failed to load logs. Please try again.");
        }

    } finally {
        hideLoader(); // Hide loader after API call completes
    }
}

function applyFilter() {
    currentPage = 0;  // Reset to first page
    fetchUserSubscriptionDetails();
}

// Fetch user subscription details
async function fetchUserSubscriptionDetails() {
    try {
        showLoader();

        const token = localStorage.getItem("x-access-token");
        if (!token) {
            logout();
            return;
        }
        const selectedUserid = document.getElementById('userFilter').value;
        const payload = {intUserId : selectedUserid};

        const response = await fetch("/api/nubot/amadeus-air-ruler/get_all_users_sub_details", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-access-token": token,
            },
            body: JSON.stringify(payload)
        });

        if (await handleUnauthorized(response)) return;

        const result = await response.json();
        const tbody = document.getElementById("subscriptionTableBody"); 

        tbody.innerHTML = ""; // Clear previous data

        if (response.status === 400) {
            showModal(logs.error);
            return;
        }

        result.forEach(user => {
            let row = document.createElement("tr");
            row.innerHTML = `
                    <td>${user.slNo}</td>
                    <td>${user.strUserName || "N/A"}</td>
                    <td>${user.strEmailId || "N/A"}</td>
                    <td>${user.strSubName || "N/A"}</td>
                    <td>${user.intCreditsUsed}</td>
                    <td>${user.timStartSub}</td>
                    <td>${user.timEndSub}</td> 
                    <td>
                        <button class="choose-plan-btn" data-user-id="${user.intUserId}">
                        Choose Plan
                        </button>
                    </td>`;
                    
                tbody.appendChild(row);
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

document.addEventListener("DOMContentLoaded", async () => {
    const token = localStorage.getItem("x-access-token");
    if (!token) {
        logout();
        return;
    }
    try {
        await fetchUsers();
        await fetchUserSubscriptionDetails();
    } catch (error) {
        console.error("Initialization error:", error);
        logout();
    }
});


function closeModal() {
    document.getElementById("messageModal").style.display = "none";
}


function showModal(message) {
    console.log("Modal triggered with message:", message);
    document.getElementById("modalMessage").textContent = message;
    document.getElementById("messageModal").style.display = "flex";
}

function backToDashboard() {
    window.location.href = "/api/nubot/amadeus-air-ruler/dashboard"; // Adjust this URL if your dashboard route is different.
}