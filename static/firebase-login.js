const firebaseConfig = {
    apiKey: "AIzaSyCuglc7ZGBb6ICnqsOg9pVeojNhgythB8k",
    authDomain: "assignment-2-c9bd8.firebaseapp.com",
    projectId: "assignment-2-c9bd8",
    storageBucket: "assignment-2-c9bd8.appspot.com",
    messagingSenderId: "396518114321",
    appId: "1:396518114321:web:7a578f739dec44d1d39db0"
  };
  
  firebase.initializeApp(firebaseConfig);
  const auth = firebase.auth();
  
 
  function login() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
  
    if (!email || !password) {
      alert("Please enter both email and password.");
      return;
    }
  
    auth.createUserWithEmailAndPassword(email, password)
    .then((userCredential) => {
      return userCredential.user.getIdToken().then((idToken) => {
        document.cookie = `token=${idToken}; path=/; max-age=3600; SameSite=Lax`;
        console.log("✅ Signup successful. Token stored.");
        window.location.href = "/dashboard";  
      });
    })
    .catch((error) => {
      console.error("❌ Signup Error:", error.message);
      document.getElementById("error-message").innerText = error.message;
    });  
  }
  
 
  function signup() {
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
  
    if (!email || !password) {
      alert("Please enter both email and password.");
      return;
    }
  
    auth.createUserWithEmailAndPassword(email, password)
      .then(() => {
        alert("Signup successful! You can now log in.");
        window.location.href = '/login';
      })
      .catch((error) => {
        console.error("❌ Signup Error:", error.message);
        document.getElementById("error-message").innerText = error.message;
      });
  }
  
  
  function logout() {
    auth.signOut().then(() => {
      document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC";
      window.location.reload();
    });
  }
  
 
  auth.onAuthStateChanged((user) => {
    if (user) {
      console.log("✅ User is logged in:", user.email);
      const emailSpan = document.getElementById("user-email");
      if (emailSpan) emailSpan.innerText = user.email;
  
      const logoutBtn = document.getElementById("logout-btn");
      if (logoutBtn) logoutBtn.style.display = "block";
    } else {
      console.log("❌ User is logged out.");
      const emailSpan = document.getElementById("user-email");
      if (emailSpan) emailSpan.innerText = "Guest";
  
      const logoutBtn = document.getElementById("logout-btn");
      if (logoutBtn) logoutBtn.style.display = "none";
    }
  });
  