function addRow() {
    let div = document.createElement("div");
    div.className = "row";
    div.innerHTML = `
        Product ID: <input name="product_id[]" required>
        Qty: <input type="number" name="qty[]" value="1" min="1">
    `;
    document.getElementById("products").appendChild(div);
}
