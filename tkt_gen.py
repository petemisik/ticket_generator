from PIL import Image, ImageDraw, ImageFont
import os
import io

try:
    from fpdf import FPDF
except ImportError:
    print("FPDF2 library not found. Please install it: pip install fpdf2")
    print("PDF output will not be available.")
    FPDF = None

DEBUG_ROTATED_TEXT = False # Set to False to turn off debug prints and image saving

# --- Configuration (Ticket Design) ---
TICKET_WIDTH_PX = 450  # Increased width a bit to accommodate stub better
TICKET_HEIGHT_PX = 200
STUB_WIDTH_PX = 100    # Width of the stub area for the rotated number
IMAGE_ON_TICKET_HEIGHT_PX = 70 # Height of the image on the ticket in pixels
NUMBER_FONT_SIZE = 24  # Font size for the main (rotated) ticket number
TEXT_FONT_SIZE = 18    # Font size for other smaller texts
FONT_PATH = "arial.ttf"
TEXT_COLOR = (0, 0, 0)
BACKGROUND_COLOR = (255, 255, 255)
TICKET_BORDER_COLOR = (150, 150, 150)
TICKET_BORDER_WIDTH = 2
ROTATED_NUMBER_ANGLE = -90 # -90 for top-to-bottom, 90 for bottom-to-top

ROTATED_NUMBER_X_OFFSET_STUB_PX = 15

# --- PDF Sheet Layout Configuration (same as before) ---
PDF_TICKETS_PER_ROW = 2
PDF_TICKETS_PER_COL = 4
PDF_PAGE_ORIENTATION = 'P'
PDF_PAGE_FORMAT = 'A4'
PDF_MARGIN_PT = 36
PDF_SPACING_PT = 10
EFFECTIVE_DPI_FOR_CONVERSION = 96.0

# --- Helper Functions ---

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        print(f"Error: Font file not found at '{FONT_PATH}'. Using default font.")
        return ImageFont.load_default()

def draw_rotated_text(image, text, center_position, font, fill, angle):
    """
    Draws rotated text onto the image, cropping to actual pixels first.
    """
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1,1))) # For textbbox/textsize
    try:
        # Get initial dimensions using textbbox
        bbox = dummy_draw.textbbox((0,0), text, font=font)
        text_width_initial = bbox[2] - bbox[0]
        text_height_initial = bbox[3] - bbox[1]
    except AttributeError: # Fallback for older Pillow
        text_width_initial, text_height_initial = dummy_draw.textsize(text, font=font)

    # Ensure minimum dimensions to avoid errors if text is empty or font is tiny
    text_width_initial = max(1, text_width_initial)
    text_height_initial = max(1, text_height_initial)

    if DEBUG_ROTATED_TEXT:
        print(f"--- Rotated Text Debug for '{text}' ---")
        print(f"Initial estimated: width={text_width_initial}, height={text_height_initial}")

    # Create a temporary RGBA canvas for drawing the text.
    # Add a little padding to ensure getbbox captures everything if text touches edges.
    padding = 5
    canvas_width = text_width_initial + 2 * padding
    canvas_height = text_height_initial + 2 * padding
    
    txt_canvas_img = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    draw_on_canvas = ImageDraw.Draw(txt_canvas_img)
    # Draw the text onto this temporary canvas (at an offset due to padding)
    draw_on_canvas.text((padding, padding), text, font=font, fill=fill)

    # Get the bounding box of the actual drawn pixels on the canvas
    actual_content_bbox = txt_canvas_img.getbbox()

    if actual_content_bbox:
        # Crop the canvas to this bounding box
        txt_img_cropped = txt_canvas_img.crop(actual_content_bbox)
    else:
        # If text is empty or invisible, create a minimal 1x1 transparent image
        if DEBUG_ROTATED_TEXT: print("Warning: actual_content_bbox was None. Text might be empty or invisible.")
        txt_img_cropped = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        
    if DEBUG_ROTATED_TEXT:
        print(f"Cropped unrotated: width={txt_img_cropped.width}, height={txt_img_cropped.height}")
        try:
            # Sanitize filename for saving
            safe_text_fn = "".join(c if c.isalnum() else "_" for c in text[:20]) # Limit length
            txt_img_cropped.save(f"debug_text_cropped_unrotated_{safe_text_fn}.png")
        except Exception as e:
            print(f"Could not save debug_text_cropped_unrotated: {e}")

    # Rotate the CROPPED image
    rotated_txt_img = txt_img_cropped.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    if DEBUG_ROTATED_TEXT:
        print(f"Rotated final: width={rotated_txt_img.width}, height={rotated_txt_img.height}")
        try:
            rotated_txt_img.save(f"debug_text_rotated_final_{safe_text_fn}.png")
        except Exception as e:
            print(f"Could not save debug_text_rotated_final: {e}")
            
    # Calculate top-left position for pasting, so the CENTER of rotated_txt_img is at 'center_position'
    paste_x = center_position[0] - rotated_txt_img.width // 2
    paste_y = center_position[1] - rotated_txt_img.height // 2

    if DEBUG_ROTATED_TEXT:
        print(f"Target center_position: {center_position}")
        print(f"Calculated paste_x: {paste_x}, paste_y: {paste_y}")
        # Important: What are the ticket's dimensions?
        print(f"Pasting onto image of size: width={image.width}, height={image.height}")
        print(f"------------------------------------")

    # Paste using the alpha channel of rotated_txt_img as a mask
    image.paste(rotated_txt_img, (int(paste_x), int(paste_y)), rotated_txt_img)

def create_ticket_front(number_str, image_path, logo_image_height_px):
    ticket = Image.new("RGB", (TICKET_WIDTH_PX, TICKET_HEIGHT_PX), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(ticket)

    # --- Draw Border ---
    if TICKET_BORDER_WIDTH > 0:
        draw.rectangle(
            [(0,0), (TICKET_WIDTH_PX - 1, TICKET_HEIGHT_PX - 1)],
            outline=TICKET_BORDER_COLOR,
            width=TICKET_BORDER_WIDTH
        )
        # Optional: draw a perforation line for the stub
        if STUB_WIDTH_PX > 0 and STUB_WIDTH_PX < TICKET_WIDTH_PX:
            line_x = STUB_WIDTH_PX
            for y_dash in range(TICKET_BORDER_WIDTH, TICKET_HEIGHT_PX - TICKET_BORDER_WIDTH, 10): # Dashed line
                draw.line([(line_x, y_dash), (line_x, y_dash + 5)], fill=TICKET_BORDER_COLOR, width=1)


    # --- 1. Rotated Number on Stub ---
    number_font = load_font(NUMBER_FONT_SIZE)
    base_stub_center_x = STUB_WIDTH_PX // 2
    final_stub_center_x = base_stub_center_x + ROTATED_NUMBER_X_OFFSET_STUB_PX # Apply the offset
    stub_center_y = TICKET_HEIGHT_PX // 2
    draw_rotated_text(ticket, number_str, (final_stub_center_x, stub_center_y),
                      number_font, TEXT_COLOR, ROTATED_NUMBER_ANGLE)

    # --- Define Main Body Area (to the right of the stub) ---
    main_body_x_start = STUB_WIDTH_PX + (PDF_SPACING_PT // 2 if STUB_WIDTH_PX > 0 else 0) # Add a little gap
    main_body_width = TICKET_WIDTH_PX - main_body_x_start - (PDF_SPACING_PT // 2)
    main_body_center_x = main_body_x_start + main_body_width // 2

    # --- 2. Load and Place Logo in Main Body ---
    logo = None
    if image_path: # Only try to load if a path is given
        try:
            logo_original = Image.open(image_path).convert("RGBA")
            aspect_ratio = logo_original.width / logo_original.height
            logo_height_px_actual = logo_image_height_px
            logo_width_px = int(logo_height_px_actual * aspect_ratio)
            if logo_width_px > main_body_width * 0.8: # Cap width if too large for main body
                logo_width_px = int(main_body_width * 0.8)
                logo_height_px_actual = int(logo_width_px / aspect_ratio)

            logo = logo_original.resize((logo_width_px, logo_height_px_actual), Image.Resampling.LANCZOS)

            logo_paste_x = main_body_center_x - logo.width // 2
            logo_paste_y = (TICKET_HEIGHT_PX // 2) - logo.height // 2 # Vertically center logo in ticket
            ticket.paste(logo, (logo_paste_x, logo_paste_y), logo)
        except FileNotFoundError:
            print(f"Warning: Logo image '{image_path}' not found. Skipping logo.")
        except Exception as e:
            print(f"Warning: Could not load or resize logo: {e}. Skipping logo.")

    # --- 3. Optional: Add other text elements to Main Body ---
    small_font = load_font(TEXT_FONT_SIZE)
    
    # "EVENT TICKET" text - top of main body
    event_text_y = 15
    try:
        draw.text((main_body_center_x, event_text_y), "EVENT TICKET", font=small_font, fill=TEXT_COLOR, anchor="mt")
    except TypeError: # Fallback for older Pillow
        et_w, _ = draw.textsize("EVENT TICKET", font=small_font)
        draw.text((main_body_center_x - et_w // 2, event_text_y), "EVENT TICKET", font=small_font, fill=TEXT_COLOR)

    # Small "No. {number_str}" - bottom of main body
    num_text_y = TICKET_HEIGHT_PX - 15
    try:
        draw.text((main_body_center_x, num_text_y), f"No. {number_str}", font=small_font, fill=TEXT_COLOR, anchor="mb")
    except TypeError:
        ns_w, ns_h = draw.textsize(f"No. {number_str}", font=small_font)
        draw.text((main_body_center_x - ns_w // 2, num_text_y - ns_h), f"No. {number_str}", font=small_font, fill=TEXT_COLOR)

    return ticket

def create_ticket_back(number_str):
    ticket = Image.new("RGB", (TICKET_WIDTH_PX, TICKET_HEIGHT_PX), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(ticket)

    if TICKET_BORDER_WIDTH > 0:
        draw.rectangle(
            [(0,0), (TICKET_WIDTH_PX - 1, TICKET_HEIGHT_PX - 1)],
            outline=TICKET_BORDER_COLOR,
            width=TICKET_BORDER_WIDTH
        )

    text_font = load_font(TEXT_FONT_SIZE)
    text_y_spacing = TEXT_FONT_SIZE + 10 # Approximate spacing
    current_y = 30 # Starting Y position for text

    # --- Draw "TICKET BACK" centered ---
    try:
        # Use anchor for single line text if available
        draw.text((TICKET_WIDTH_PX // 2, current_y), "TICKET BACK", font=text_font, fill=TEXT_COLOR, anchor="mt")
        # To get the height of this text for spacing:
        bbox_tb = draw.textbbox((TICKET_WIDTH_PX // 2, current_y), "TICKET BACK", font=text_font, anchor="mt")
        current_y += (bbox_tb[3] - bbox_tb[1]) + text_y_spacing // 2 # Add height + half spacing
    except TypeError: # Fallback for older Pillow or if anchor="mt" causes issues
        tb_w, tb_h = draw.textsize("TICKET BACK", font=text_font)
        draw.text(((TICKET_WIDTH_PX - tb_w) // 2, current_y), "TICKET BACK", font=text_font, fill=TEXT_COLOR)
        current_y += tb_h + text_y_spacing // 2

    # --- Draw "Terms and Conditions" centered (multiline) ---
    terms_text = "Terms and Conditions Apply.\nVisit website for details."
    
    # Get the bounding box for the multiline text to center it
    # We need to draw it at (0,0) on a dummy canvas first to get its total width and height
    # Or use textbbox if available and reliable for multiline without anchor
    try:
        # For multiline, textbbox still works to get dimensions without anchor
        bbox_terms = draw.multiline_textbbox((0, 0), terms_text, font=text_font, spacing=4, align="center")
        multiline_width = bbox_terms[2] - bbox_terms[0]
        multiline_height = bbox_terms[3] - bbox_terms[1]
    except AttributeError: # Fallback for older Pillow or if multiline_textbbox is not as expected
        # Fallback: calculate approximate height
        lines = terms_text.splitlines()
        max_w = 0
        total_h = 0
        line_spacing = 4 # Manually set spacing if not using Pillow's spacing param
        for i, line in enumerate(lines):
            lw, lh = draw.textsize(line, font=text_font)
            if lw > max_w:
                max_w = lw
            total_h += lh
            if i < len(lines) -1:
                total_h += line_spacing
        multiline_width = max_w
        multiline_height = total_h

    x_terms = (TICKET_WIDTH_PX - multiline_width) // 2
    # Place it, for example, some pixels below the previous text
    # current_y is already updated after "TICKET BACK"
    draw.multiline_text((x_terms, current_y), terms_text, font=text_font, fill=TEXT_COLOR, align="center", spacing=4)
    current_y += multiline_height + text_y_spacing

    # --- Draw "Serial: {number_str}" centered at bottom ---
    # Position this relative to the bottom of the ticket
    serial_y_bottom_margin = 30 # Margin from the bottom
    try:
        # Use anchor for single line text if available, "mb" for middle-bottom alignment
        bbox_serial = draw.textbbox((TICKET_WIDTH_PX // 2, TICKET_HEIGHT_PX - serial_y_bottom_margin), f"Serial: {number_str}", font=text_font, anchor="mb")
        draw.text((TICKET_WIDTH_PX // 2, TICKET_HEIGHT_PX - serial_y_bottom_margin), f"Serial: {number_str}", font=text_font, fill=TEXT_COLOR, anchor="mb")
    except TypeError: # Fallback
        sn_w, sn_h = draw.textsize(f"Serial: {number_str}", font=text_font)
        draw.text(((TICKET_WIDTH_PX - sn_w) // 2, TICKET_HEIGHT_PX - serial_y_bottom_margin - sn_h), f"Serial: {number_str}", font=text_font, fill=TEXT_COLOR)
    
    return ticket

# --- PDF Generation Function (generate_pdf_from_images - same as before) ---
def generate_pdf_from_images(ticket_pil_images, output_filename="ticket_sheet.pdf"):
    if FPDF is None:
        print("FPDF library not available. Cannot generate PDF.")
        return

    ticket_width_pt = TICKET_WIDTH_PX * 72.0 / EFFECTIVE_DPI_FOR_CONVERSION
    ticket_height_pt = TICKET_HEIGHT_PX * 72.0 / EFFECTIVE_DPI_FOR_CONVERSION

    pdf = FPDF(orientation=PDF_PAGE_ORIENTATION, unit='pt', format=PDF_PAGE_FORMAT)
    pdf.set_auto_page_break(False)

    tickets_per_page = PDF_TICKETS_PER_ROW * PDF_TICKETS_PER_COL
    ticket_index_on_page = 0

    for i, pil_image in enumerate(ticket_pil_images):
        if ticket_index_on_page == 0:
            pdf.add_page()
            if i == 0:
                required_width = (PDF_TICKETS_PER_ROW * ticket_width_pt) + \
                                 ((PDF_TICKETS_PER_ROW - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_ROW > 1 else 0) + \
                                 2 * PDF_MARGIN_PT
                required_height = (PDF_TICKETS_PER_COL * ticket_height_pt) + \
                                  ((PDF_TICKETS_PER_COL - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_COL > 1 else 0) + \
                                  2 * PDF_MARGIN_PT
                if required_width > pdf.w:
                    print(f"Warning: Calculated width ({required_width:.2f}pt) for tickets on page exceeds PDF page width ({pdf.w:.2f}pt).")
                if required_height > pdf.h:
                    print(f"Warning: Calculated height ({required_height:.2f}pt) for tickets on page exceeds PDF page height ({pdf.h:.2f}pt).")

        col_num = ticket_index_on_page % PDF_TICKETS_PER_ROW
        row_num = ticket_index_on_page // PDF_TICKETS_PER_ROW
        x_pt = PDF_MARGIN_PT + col_num * (ticket_width_pt + PDF_SPACING_PT)
        y_pt = PDF_MARGIN_PT + row_num * (ticket_height_pt + PDF_SPACING_PT)

        with io.BytesIO() as img_byte_stream:
            pil_image.save(img_byte_stream, format="PNG")
            img_byte_stream.seek(0)
            pdf.image(img_byte_stream, x=x_pt, y=y_pt, w=ticket_width_pt, h=ticket_height_pt, type="PNG")

        ticket_index_on_page += 1
        if ticket_index_on_page >= tickets_per_page:
            ticket_index_on_page = 0

    pdf.output(output_filename, "F")
    print(f"Saved PDF: {output_filename}")


# --- Main Execution (same as before) ---
if __name__ == "__main__":
    start_number = int(input("Enter starting ticket number: "))
    end_number = int(input("Enter ending ticket number: "))
    image_file_path = input("Enter path to the image for the ticket center (now for main body): ")
    num_leading_zeros = int(input("Enter number of leading zeros for ticket numbers (e.g., 5 for 00001): "))

    if not (os.path.exists(image_file_path) or image_file_path.strip() == ""): # Allow empty path for no logo
        print(f"Error: Image file '{image_file_path}' not found. Exiting.")
        exit()
    if image_file_path.strip() == "":
        print("No image path provided. Tickets will be generated without a central image.")
        image_file_path = None # Set to None if empty

    if FPDF is None:
        print("FPDF2 library is not installed. PDF output is disabled. Exiting.")
        exit()
    
    if start_number > end_number:
        print("Error: Start number cannot be greater than end number. Exiting.")
        exit()

    all_front_pil_images = []
    all_back_pil_images = []

    print("\nGenerating ticket images (using Pillow)...")
    total_tickets = end_number - start_number + 1
    for count, i in enumerate(range(start_number, end_number + 1)):
        number_string = str(i).zfill(num_leading_zeros)
        if (count + 1) % 10 == 0 or (count + 1) == 1 or (count + 1) == total_tickets :
             print(f"  Creating ticket No. {number_string} ({(count + 1)} of {total_tickets})")

        front_pil = create_ticket_front(number_string, image_file_path, IMAGE_ON_TICKET_HEIGHT_PX)
        all_front_pil_images.append(front_pil)

        back_pil = create_ticket_back(number_string)
        all_back_pil_images.append(back_pil)

    print(f"\nGenerated {len(all_front_pil_images)} ticket images with Pillow.")

    if FPDF is not None:
        print("\nGenerating PDF files...")
        if all_front_pil_images:
            generate_pdf_from_images(all_front_pil_images, "ticket_sheet_fronts.pdf")
            generate_pdf_from_images(all_back_pil_images, "ticket_sheet_backs.pdf")
            print("\nPDF generation complete.")
            print("To print double-sided: print 'ticket_sheet_fronts.pdf', then flip the paper appropriately and print 'ticket_sheet_backs.pdf' on the other side.")
        else:
            print("No ticket images were generated, so no PDF will be created.")
    else:
        print("Skipping PDF generation as FPDF2 is not installed or failed to import.")

    print("\nDone!")