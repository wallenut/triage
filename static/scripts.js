// var login = document.getElementById("login");
var register = document.getElementById("register");

// login.onsubmit = function()
// {
//     if(login.username.value == ''){
//         alert("No email provided");
//         return false;
//     }
//     else if(login.password.value == ''){
//         alert("No password provided");
//         return false;
//     }
// };

register.onsubmit = function()
{
    if(register.username.value == ''){
        alert("No username provided");
        return false;
    }
    else if(register.password.value == '') {
        alert("No password provided");
        return false;
    }
    else if(register.password.value != register.confirmation.value){
        alert("Passwords don't match");
        return false;
    }
};