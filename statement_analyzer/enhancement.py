import io
from PIL import Image
import cv2
import numpy as np
from pdf2image import convert_from_bytes # Ensure poppler is installed for pdf2image
from PyPDF2 import PdfReader # Use PdfReader for reading PDF documents
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image

# --- Core Functions ---

def convert_pdf_to_images(pdf_object_bytesio):
    """
    Converts a BytesIO object containing PDF data into a list of PIL Image objects.

    Args:
        pdf_object_bytesio (io.BytesIO): A BytesIO object containing the PDF data.

    Returns:
        List[PIL.Image.Image]: A list of PIL Image objects, one for each page of the PDF.
    """
    # Important: Always seek to the beginning of the BytesIO object before reading its content.
    pdf_object_bytesio.seek(0)
    # convert_from_bytes reads the entire byte stream of the PDF.
    images = convert_from_bytes(pdf_object_bytesio.read())
    print(f"  -> Converted {len(images)} pages from PDF to images.")
    return images


def fix_skew_on_images(images):
    fixed_images = []
    for i, image in enumerate(images):
        open_cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

        # Thresholding
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(binary > 0))

        if coords.size == 0:
            fixed_images.append(image)
            print(f"[Skipped deskew] Blank page detected at index {i}")
            continue

        angle = cv2.minAreaRect(coords)[-1]

        # Fix the rotation angle
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90

        # Only rotate if skew is significant (e.g., > 0.5°)
        if abs(angle) > 0.5:
            (h, w) = open_cv_image.shape[:2]
            center = (w // 2, h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(open_cv_image, rotation_matrix, (w, h),
                                     flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            result_image = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
        else:
            result_image = image  # No rotation needed

        fixed_images.append(result_image)

    print(f"✅ Fixed skew on {len(fixed_images)} images.")
    return fixed_images




def create_pdf_from_images(image_list, file_name="combined.pdf"):
    # Ensure all images are in RGB mode
    rgb_images = [img.convert("RGB") for img in image_list]

    # Create a BytesIO buffer to hold PDF data
    pdf_buffer = io.BytesIO()
    
    # Save images into the buffer as a single PDF
    rgb_images[0].save(
        pdf_buffer,
        format="PDF",
        save_all=True,
        append_images=rgb_images[1:]
    )

    # Seek to the beginning of the buffer
    pdf_buffer.seek(0)

    # Create InMemoryUploadedFile from buffer
    uploaded_pdf = InMemoryUploadedFile(
        file=pdf_buffer,
        field_name="file",
        name=file_name,
        content_type="application/pdf",
        size=pdf_buffer.getbuffer().nbytes,
        charset=None
    )

    return uploaded_pdf


def save_images_to_pdf_object(images):
    """
    Convert a list of PIL images to a single PDF file object in memory.

    Args:
        images (List[PIL.Image.Image]): List of PIL image objects.
                                        Images should ideally be of the same size
                                        for consistent PDF pages, but Pillow can
                                        handle different sizes by fitting them.

    Returns:
        io.BytesIO: PDF file-like object containing all the images as separate pages.
                    This object can then be saved to a file or sent over a network.
    """
    # Create a BytesIO object to store the PDF in memory.
    pdf_buffer = io.BytesIO()

    # Handle case where no images are provided.
    if not images:
        print("  -> Warning: No images provided to convert to PDF. Returning an empty buffer.")
        return pdf_buffer

    try:
        # This is the crucial line for multi-page PDF creation:
        # - images[0].save(): Initiates the PDF document with the first image.
        # - format='PDF': Specifies the output format.
        # - save_all=True: Tells Pillow that multiple pages will be saved.
        # - append_images=images[1:]: Appends all subsequent images from the list
        #   as new pages to the PDF document.
        images[0].save(pdf_buffer, format='PDF', save_all=True, append_images=images[1:])
    except Exception as e:
        print(f"  -> Error converting images to PDF: {e}")
        raise # Re-raise the exception after printing for visibility.

    # Rewind the buffer's pointer to the beginning. This is essential so that
    # any subsequent read operations (like by PyPDF2 or for saving to file)
    # can access the entire PDF content from the start.
    pdf_buffer.seek(0)
    print(f"  -> Saved {len(images)} images to a new PDF BytesIO object.")
    return pdf_buffer


def enhancement_logic(pdf_object_bytesio):
    """
    Enhances the PDF by fixing skew and returns it as a new BytesIO object.

    Args:
        pdf_object_bytesio (io.BytesIO): A BytesIO object containing the PDF data to be enhanced.

    Returns:
        io.BytesIO: A new BytesIO object containing the enhanced (deskewed) PDF data.
    """
    print("\n--- Starting enhancement logic ---")
    # Convert PDF to images. This function handles seeking the input pdf_object_bytesio.
    images = convert_pdf_to_images(pdf_object_bytesio)

    # Fix skew on images.
    fixed_images = fix_skew_on_images(images)

    # Save the fixed images back to a *new* PDF BytesIO object.
    # It's important to understand this function returns a completely new BytesIO object,
    # leaving the original input pdf_object_bytesio as it was (though its pointer might be at end).
    enhanced_pdf_object = create_pdf_from_images(fixed_images)
    print("--- Enhancement logic completed ---")
    return enhanced_pdf_object