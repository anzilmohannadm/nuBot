const socket = io();
const messageForm = document.getElementById("message-form");
const messageInput = document.getElementById("message-input");
const messages = document.getElementById("messages");

function displayMessage(role, message) {
  const div = document.createElement("div");
  const messageClass = role === "user" ? "user-message" : "assistant-message";
  div.classList.add(messageClass);
  div.innerHTML = message;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

messageForm.addEventListener("submit", (e) => {
  e.preventDefault();

  const message = messageInput.value;
  messageInput.value = "";
  messageInput.focus();
  displayMessage("user", message); // Display user's message in the chat
  socket.emit("message", message, (error) => {
    if (error) {
      return alert(error);
    }
  });
});

socket.on("message", (message) => {
  displayMessage("assistant", message); // Display assistant's message in the chat
});