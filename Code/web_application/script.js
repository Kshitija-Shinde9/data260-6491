// keeping a running count of submissions here, this stays private and only the counter can touch it
const submissionCounter = (() => {
    let count = 0;
    return () => {
        count = count + 1;
        return count;
    };
})();

// two checks in one place, description length and the checkbox. throwing an alert if either one is off
const validateForm = (descriptionValue, isChecked) => {
    const trimmedDescription = descriptionValue.trim();

    if (trimmedDescription.length <= 25) {
        alert("please write a bit more in the recall reason, needs to be more than 25 characters");
        return false;
    }

    if (!isChecked) {
        alert("you need to check the box agreeing to the terms and conditions before submitting");
        return false;
    }

    return true;
};

document.getElementById("recallForm").addEventListener("submit", (event) => {
    event.preventDefault();

    // trimming everything on the way in so stray spaces don't sneak through as real input
    const productName = document.getElementById("productName").value.trim();
    const supplierName = document.getElementById("supplierName").value.trim();
    const submitterEmail = document.getElementById("submitterEmail").value.trim();
    const recallDescription = document.getElementById("recallDescription").value.trim();
    const recallType = document.getElementById("recallType").value;
    const agreeTerms = document.getElementById("agreeTerms").checked;

    // if this comes back false just stop right here, nothing below should run
    const isValid = validateForm(recallDescription, agreeTerms);
    if (!isValid) {
        return;
    }

    const formData = {
        productName: productName,
        supplierName: supplierName,
        submitterEmail: submitterEmail,
        recallDescription: recallDescription,
        recallType: recallType
    };

    const jsonString = JSON.stringify(formData);
    console.log("form data as JSON string:", jsonString);

    const parsedData = JSON.parse(jsonString);

    // just pulling out product name and email here, renaming them so it reads a bit clearer
    const { productName: reportedProduct, submitterEmail: reportedEmail } = parsedData;
    console.log("product name:", reportedProduct);
    console.log("submitter email:", reportedEmail);

    // copying everything over and tacking on when this actually got submitted
    const updatedData = { ...parsedData, submissionDate: new Date().toString() };
    console.log("updated data with submission date:", updatedData);

    const currentCount = submissionCounter();
    console.log("this form has been submitted", currentCount, "time(s) so far");

    alert("thanks, your recall report was submitted");

    // clearing everything out so the form is ready to go again
    document.getElementById("recallForm").reset();
});