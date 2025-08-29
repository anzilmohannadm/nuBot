document.getElementById("loginForm").addEventListener("submit", async function (event) {
    event.preventDefault();

    let email = document.getElementById("email").value;
    let password = document.getElementById("password").value;

    try {
        let response = await fetch("/api/nubot/amadeus-air-ruler/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        let result = await response.json();

        if (response.status === 200) {
            if (result.token) {
                // Store token and redirect to dashboard
                localStorage.setItem("x-access-token", result.token);
                
                let checkPermissionResponse = await fetch("/api/nubot/amadeus-air-ruler/check_permissions", {
                    method: "POST", // Change to POST
                    headers: { 
                        "Content-Type": "application/json",
                        "x-access-token": result.token
                    }
                })

                if (checkPermissionResponse.status === 200) {
                    window.location.href = "/api/nubot/amadeus-air-ruler/dashboard"; 
                    
                } else {
                    showModal("No permissions found for this user");
                }
                
            }
        } else if (response.status === 401) {
            showModal("Invalid credentials! Please check your email and password.");
        } else {
            showModal("Login failed. Please try again.");
        }
    } catch (error) {
        console.error("Error:", error);
        showModal("Something went wrong. Please try again.");
    }
});

function showModal(message) {
    document.getElementById("modalMessage").textContent = message;
    document.getElementById("messageModal").style.display = "flex";
}

function closeModal() {
    document.getElementById("messageModal").style.display = "none";
}