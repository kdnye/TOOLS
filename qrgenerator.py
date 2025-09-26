import qrcode

# Data to encode
data = "https://github.com/kdnye/"

# Generate QR code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=10,
    border=4,
)
qr.add_data(data)
qr.make(fit=True)

# Create image
img = qr.make_image(fill_color="black", back_color="white")

# Save QR code to file
file_path = "/home/dave/github_qrcode.png"
img.save(file_path)

file_path
