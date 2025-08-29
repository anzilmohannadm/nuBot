document.addEventListener("DOMContentLoaded", () => {
    const token = localStorage.getItem("x-access-token");

    document.getElementById("userMenu").addEventListener("click", () => {
        // Navigate to the user subscription details page
        window.location.href = "/api/nubot/amadeus-air-ruler/get_all_users_sub_details"; // Adjust the path accordingly
    });

    document.getElementById("logsMenu").addEventListener("click", () => {
        window.location.href = "/api/nubot/amadeus-air-ruler/get_all_logs"; // Adjust path if needed
    });
});

function logout() {
    // Remove token from localStorage
    localStorage.removeItem("x-access-token");
    // Redirect to login page
    window.location.href = "/api/nubot/amadeus-air-ruler/login"; // Change this to your login route
}