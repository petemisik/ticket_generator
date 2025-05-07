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

# --- Scaling Factor ---
SCALE_FACTOR = 0.5  # Set to 0.5 for half size, adjust as needed

# --- Original Configuration (Ticket Design) ---
# These are the design values for the "full-size" ticket
ORIG_TICKET_WIDTH_PX = 450
ORIG_TICKET_HEIGHT_PX = 200
ORIG_STUB_WIDTH_PX = 100
ORIG_IMAGE_ON_TICKET_HEIGHT_PX = 70
ORIG_NUMBER_FONT_SIZE = 24
ORIG_TEXT_FONT_SIZE = 18
ORIG_TICKET_BORDER_WIDTH = 2
ORIG_ROTATED_NUMBER_X_OFFSET_STUB_PX = 15

# Original spacing/padding values (some were implicit or based on PDF settings)
ORIG_ROTATED_TEXT_PADDING_PX = 5       # Padding for rotated text canvas
ORIG_MAIN_BODY_MARGIN_PX = 6           # Approx. (PDF_SPACING_PT/2) -> 5pt * 96/72 = 6.6px, round to 6px
ORIG_FRONT_TEXT_TOP_MARGIN_PX = 15
ORIG_FRONT_TEXT_BOTTOM_MARGIN_PX = 15
ORIG_BACK_TEXT_START_Y_PX = 30
ORIG_BACK_TEXT_LINE_SPACING_ADDON_PX = 10 # Additional spacing beyond font height for back text lines
ORIG_BACK_MULTILINE_SPACING_PX = 4     # Line spacing within multiline text on back
ORIG_BACK_SERIAL_BOTTOM_MARGIN_PX = 30
ORIG_PERFORATION_DASH_STEP_PX = 10     # Step for perforation dashes (dash + gap)
ORIG_PERFORATION_DASH_LENGTH_PX = 5    # Length of perforation dash

# --- Scaled Configuration (Ticket Design) ---
# These are the actual values used for drawing, derived by scaling the originals
TICKET_WIDTH_PX = int(ORIG_TICKET_WIDTH_PX * SCALE_FACTOR)
TICKET_HEIGHT_PX = int(ORIG_TICKET_HEIGHT_PX * SCALE_FACTOR)
STUB_WIDTH_PX = int(ORIG_STUB_WIDTH_PX * SCALE_FACTOR)
IMAGE_ON_TICKET_HEIGHT_PX = int(ORIG_IMAGE_ON_TICKET_HEIGHT_PX * SCALE_FACTOR)
NUMBER_FONT_SIZE = max(8, int(ORIG_NUMBER_FONT_SIZE * SCALE_FACTOR))  # Min font size 8 for readability
TEXT_FONT_SIZE = max(6, int(ORIG_TEXT_FONT_SIZE * SCALE_FACTOR))     # Min font size 6
TICKET_BORDER_WIDTH = max(1, int(ORIG_TICKET_BORDER_WIDTH * SCALE_FACTOR)) if ORIG_TICKET_BORDER_WIDTH > 0 else 0
ROTATED_NUMBER_X_OFFSET_STUB_PX = int(ORIG_ROTATED_NUMBER_X_OFFSET_STUB_PX * SCALE_FACTOR)

# Scaled spacing/padding values
ROTATED_TEXT_PADDING_PX = max(2, int(ORIG_ROTATED_TEXT_PADDING_PX * SCALE_FACTOR))
MAIN_BODY_MARGIN_PX = max(2, int(ORIG_MAIN_BODY_MARGIN_PX * SCALE_FACTOR))
FRONT_TEXT_TOP_MARGIN_PX = max(5, int(ORIG_FRONT_TEXT_TOP_MARGIN_PX * SCALE_FACTOR))
FRONT_TEXT_BOTTOM_MARGIN_PX = max(5, int(ORIG_FRONT_TEXT_BOTTOM_MARGIN_PX * SCALE_FACTOR))
BACK_TEXT_START_Y_PX = max(10, int(ORIG_BACK_TEXT_START_Y_PX * SCALE_FACTOR))
BACK_TEXT_LINE_SPACING_ADDON_PX = max(3, int(ORIG_BACK_TEXT_LINE_SPACING_ADDON_PX * SCALE_FACTOR))
BACK_MULTILINE_SPACING_PX = max(1, int(ORIG_BACK_MULTILINE_SPACING_PX * SCALE_FACTOR))
BACK_SERIAL_BOTTOM_MARGIN_PX = max(10, int(ORIG_BACK_SERIAL_BOTTOM_MARGIN_PX * SCALE_FACTOR))
PERFORATION_DASH_STEP_PX = max(4, int(ORIG_PERFORATION_DASH_STEP_PX * SCALE_FACTOR)) # Ensure step > length
PERFORATION_DASH_LENGTH_PX = max(1, int(ORIG_PERFORATION_DASH_LENGTH_PX * SCALE_FACTOR))
if PERFORATION_DASH_LENGTH_PX >= PERFORATION_DASH_STEP_PX : # Ensure dash is shorter than step
    PERFORATION_DASH_LENGTH_PX = PERFORATION_DASH_STEP_PX // 2
    PERFORATION_DASH_LENGTH_PX = max(1, PERFORATION_DASH_LENGTH_PX)


# --- Static Configuration (Ticket Design) ---
FONT_PATH = "arial.ttf"
TEXT_COLOR = (0, 0, 0)
BACKGROUND_COLOR = (255, 255, 255)
TICKET_BORDER_COLOR = (150, 150, 150)
ROTATED_NUMBER_ANGLE = -90 # -90 for top-to-bottom, 90 for bottom-to-top

# --- PDF Sheet Layout Configuration (can remain the same, tickets will just be smaller on the page) ---
PDF_TICKETS_PER_ROW = 2
PDF_TICKETS_PER_COL = 4
PDF_PAGE_ORIENTATION = 'P'
PDF_PAGE_FORMAT = 'Letter'
PDF_MARGIN_PT = 36      # Margin around the block of tickets on the PDF page
PDF_SPACING_PT = 10     # Spacing between tickets on the PDF page
EFFECTIVE_DPI_FOR_CONVERSION = 96.0 # Used to convert PX to PT for PDF

# --- Helper Functions ---

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        print(f"Error: Font file not found at '{FONT_PATH}'. Using default font.")
        # Scale default font too, though it might not look great
        return ImageFont.load_default(size=max(6, int(size * SCALE_FACTOR))) if hasattr(ImageFont, 'load_default') and callable(getattr(ImageFont, 'load_default')) and 'size' in ImageFont.load_default.__code__.co_varnames else ImageFont.load_default()


def draw_rotated_text(image, text, center_position, font, fill, angle):
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1,1)))
    try:
        bbox = dummy_draw.textbbox((0,0), text, font=font)
        text_width_initial = bbox[2] - bbox[0]
        text_height_initial = bbox[3] - bbox[1]
    except AttributeError:
        text_width_initial, text_height_initial = dummy_draw.textsize(text, font=font)

    text_width_initial = max(1, text_width_initial)
    text_height_initial = max(1, text_height_initial)

    if DEBUG_ROTATED_TEXT:
        print(f"--- Rotated Text Debug for '{text}' ---")
        print(f"Initial estimated: width={text_width_initial}, height={text_height_initial}")

    # Use scaled padding
    padding = ROTATED_TEXT_PADDING_PX
    canvas_width = text_width_initial + 2 * padding
    canvas_height = text_height_initial + 2 * padding
    
    txt_canvas_img = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    draw_on_canvas = ImageDraw.Draw(txt_canvas_img)
    draw_on_canvas.text((padding, padding), text, font=font, fill=fill)

    actual_content_bbox = txt_canvas_img.getbbox()

    if actual_content_bbox:
        txt_img_cropped = txt_canvas_img.crop(actual_content_bbox)
    else:
        if DEBUG_ROTATED_TEXT: print("Warning: actual_content_bbox was None. Text might be empty or invisible.")
        txt_img_cropped = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        
    if DEBUG_ROTATED_TEXT:
        print(f"Cropped unrotated: width={txt_img_cropped.width}, height={txt_img_cropped.height}")
        try:
            safe_text_fn = "".join(c if c.isalnum() else "_" for c in text[:20])
            txt_img_cropped.save(f"debug_text_cropped_unrotated_{safe_text_fn}.png")
        except Exception as e:
            print(f"Could not save debug_text_cropped_unrotated: {e}")

    rotated_txt_img = txt_img_cropped.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    if DEBUG_ROTATED_TEXT:
        print(f"Rotated final: width={rotated_txt_img.width}, height={rotated_txt_img.height}")
        try:
            rotated_txt_img.save(f"debug_text_rotated_final_{safe_text_fn}.png")
        except Exception as e:
            print(f"Could not save debug_text_rotated_final: {e}")
            
    paste_x = center_position[0] - rotated_txt_img.width // 2
    paste_y = center_position[1] - rotated_txt_img.height // 2

    if DEBUG_ROTATED_TEXT:
        print(f"Target center_position: {center_position}")
        print(f"Calculated paste_x: {paste_x}, paste_y: {paste_y}")
        print(f"Pasting onto image of size: width={image.width}, height={image.height}")
        print(f"------------------------------------")

    image.paste(rotated_txt_img, (int(paste_x), int(paste_y)), rotated_txt_img)

def create_ticket_front(number_str, image_path, logo_image_height_px_target):
    ticket = Image.new("RGB", (TICKET_WIDTH_PX, TICKET_HEIGHT_PX), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(ticket)

    if TICKET_BORDER_WIDTH > 0:
        draw.rectangle(
            [(0,0), (TICKET_WIDTH_PX - 1, TICKET_HEIGHT_PX - 1)],
            outline=TICKET_BORDER_COLOR,
            width=TICKET_BORDER_WIDTH
        )
        if STUB_WIDTH_PX > 0 and STUB_WIDTH_PX < TICKET_WIDTH_PX:
            line_x = STUB_WIDTH_PX
            # Use scaled perforation dash settings
            for y_dash in range(TICKET_BORDER_WIDTH, TICKET_HEIGHT_PX - TICKET_BORDER_WIDTH, PERFORATION_DASH_STEP_PX):
                draw.line([(line_x, y_dash), (line_x, y_dash + PERFORATION_DASH_LENGTH_PX)], fill=TICKET_BORDER_COLOR, width=1)

    number_font = load_font(NUMBER_FONT_SIZE)
    base_stub_center_x = STUB_WIDTH_PX // 2
    final_stub_center_x = base_stub_center_x + ROTATED_NUMBER_X_OFFSET_STUB_PX
    stub_center_y = TICKET_HEIGHT_PX // 2
    if STUB_WIDTH_PX > 0: # Only draw if stub exists
        draw_rotated_text(ticket, number_str, (final_stub_center_x, stub_center_y),
                          number_font, TEXT_COLOR, ROTATED_NUMBER_ANGLE)

    # --- Define Main Body Area (to the right of the stub or from left edge) ---
    if STUB_WIDTH_PX > 0:
        main_body_x_start = STUB_WIDTH_PX + MAIN_BODY_MARGIN_PX
    else:
        main_body_x_start = MAIN_BODY_MARGIN_PX # Margin from left edge if no stub
    
    # Width of the content area in the main body, considering margin on its right side too
    main_body_content_area_width = TICKET_WIDTH_PX - main_body_x_start - MAIN_BODY_MARGIN_PX
    if main_body_content_area_width <= 0: # Safety for very small tickets
        main_body_content_area_width = TICKET_WIDTH_PX // 2 # fallback
        main_body_x_start = STUB_WIDTH_PX + MAIN_BODY_MARGIN_PX // 2
    
    main_body_center_x = main_body_x_start + main_body_content_area_width // 2

    if image_path:
        try:
            logo_original = Image.open(image_path).convert("RGBA")
            aspect_ratio = logo_original.width / logo_original.height
            # logo_image_height_px_target is already scaled IMAGE_ON_TICKET_HEIGHT_PX
            logo_height_px_actual = logo_image_height_px_target 
            logo_width_px = int(logo_height_px_actual * aspect_ratio)
            
            # Cap width if too large for main body content area
            if logo_width_px > main_body_content_area_width * 0.9: # Use 90% of content area
                logo_width_px = int(main_body_content_area_width * 0.9)
                logo_height_px_actual = int(logo_width_px / aspect_ratio)
            
            # Ensure height is also capped if aspect ratio is very tall
            if logo_height_px_actual > TICKET_HEIGHT_PX * 0.8:
                logo_height_px_actual = int(TICKET_HEIGHT_PX * 0.8)
                logo_width_px = int(logo_height_px_actual * aspect_ratio)


            if logo_width_px > 0 and logo_height_px_actual > 0: # Ensure dimensions are positive
                logo = logo_original.resize((logo_width_px, logo_height_px_actual), Image.Resampling.LANCZOS)
                logo_paste_x = main_body_center_x - logo.width // 2
                logo_paste_y = (TICKET_HEIGHT_PX // 2) - logo.height // 2
                ticket.paste(logo, (logo_paste_x, logo_paste_y), logo)
            else:
                print(f"Warning: Logo '{image_path}' resulted in zero dimensions after scaling. Skipping.")

        except FileNotFoundError:
            print(f"Warning: Logo image '{image_path}' not found. Skipping logo.")
        except Exception as e:
            print(f"Warning: Could not load or resize logo: {e}. Skipping logo.")

    small_font = load_font(TEXT_FONT_SIZE)
    
    # Use scaled margin for "EVENT TICKET" text
    event_text_y = FRONT_TEXT_TOP_MARGIN_PX
    try:
        draw.text((main_body_center_x, event_text_y), "EVENT TICKET", font=small_font, fill=TEXT_COLOR, anchor="mt")
    except TypeError:
        et_w, _ = draw.textsize("EVENT TICKET", font=small_font)
        draw.text((main_body_center_x - et_w // 2, event_text_y), "EVENT TICKET", font=small_font, fill=TEXT_COLOR)

    # Use scaled margin for "No. {number_str}" text
    num_text_y = TICKET_HEIGHT_PX - FRONT_TEXT_BOTTOM_MARGIN_PX
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
    # Use scaled Y start and line spacing addon
    current_y = BACK_TEXT_START_Y_PX
    text_y_spacing = TEXT_FONT_SIZE + BACK_TEXT_LINE_SPACING_ADDON_PX

    try:
        draw.text((TICKET_WIDTH_PX // 2, current_y), "TICKET BACK", font=text_font, fill=TEXT_COLOR, anchor="mt")
        bbox_tb = draw.textbbox((TICKET_WIDTH_PX // 2, current_y), "TICKET BACK", font=text_font, anchor="mt")
        current_y += (bbox_tb[3] - bbox_tb[1]) + text_y_spacing // 2
    except TypeError:
        tb_w, tb_h = draw.textsize("TICKET BACK", font=text_font)
        draw.text(((TICKET_WIDTH_PX - tb_w) // 2, current_y), "TICKET BACK", font=text_font, fill=TEXT_COLOR)
        current_y += tb_h + text_y_spacing // 2

    terms_text = "Terms and Conditions Apply.\nVisit website for details."
    # Use scaled multiline spacing
    try:
        bbox_terms = draw.multiline_textbbox((0, 0), terms_text, font=text_font, spacing=BACK_MULTILINE_SPACING_PX, align="center")
        multiline_width = bbox_terms[2] - bbox_terms[0]
        multiline_height = bbox_terms[3] - bbox_terms[1]
    except AttributeError:
        lines = terms_text.splitlines()
        max_w = 0
        total_h = 0
        for i, line in enumerate(lines):
            lw, lh = draw.textsize(line, font=text_font)
            if lw > max_w: max_w = lw
            total_h += lh
            if i < len(lines) -1: total_h += BACK_MULTILINE_SPACING_PX
        multiline_width = max_w
        multiline_height = total_h

    x_terms = (TICKET_WIDTH_PX - multiline_width) // 2
    draw.multiline_text((x_terms, current_y), terms_text, font=text_font, fill=TEXT_COLOR, align="center", spacing=BACK_MULTILINE_SPACING_PX)
    current_y += multiline_height + text_y_spacing # Use the full text_y_spacing after multiline block

    # Use scaled bottom margin for serial number
    serial_y_pos_from_bottom = TICKET_HEIGHT_PX - BACK_SERIAL_BOTTOM_MARGIN_PX
    try:
        draw.text((TICKET_WIDTH_PX // 2, serial_y_pos_from_bottom), f"Serial: {number_str}", font=text_font, fill=TEXT_COLOR, anchor="mb")
    except TypeError:
        sn_w, sn_h = draw.textsize(f"Serial: {number_str}", font=text_font)
        draw.text(((TICKET_WIDTH_PX - sn_w) // 2, serial_y_pos_from_bottom - sn_h), f"Serial: {number_str}", font=text_font, fill=TEXT_COLOR)
    
    return ticket

def generate_pdf_from_images(ticket_pil_images, output_filename="ticket_sheet.pdf"):
    if FPDF is None:
        print("FPDF library not available. Cannot generate PDF.")
        return

    # These will now use the scaled TICKET_WIDTH_PX and TICKET_HEIGHT_PX
    ticket_width_pt = TICKET_WIDTH_PX * 72.0 / EFFECTIVE_DPI_FOR_CONVERSION
    ticket_height_pt = TICKET_HEIGHT_PX * 72.0 / EFFECTIVE_DPI_FOR_CONVERSION

    pdf = FPDF(orientation=PDF_PAGE_ORIENTATION, unit='pt', format=PDF_PAGE_FORMAT)
    pdf.set_auto_page_break(False)

    tickets_per_page = PDF_TICKETS_PER_ROW * PDF_TICKETS_PER_COL
    ticket_index_on_page = 0

    for i, pil_image in enumerate(ticket_pil_images):
        if ticket_index_on_page == 0:
            pdf.add_page()
            # Warning for page overflow check (this logic remains the same, just values are smaller)
            if i == 0: # Check only for the first page setup
                page_content_width_pt = pdf.w - 2 * PDF_MARGIN_PT
                page_content_height_pt = pdf.h - 2 * PDF_MARGIN_PT

                required_width_for_tickets_pt = (PDF_TICKETS_PER_ROW * ticket_width_pt) + \
                                                ((PDF_TICKETS_PER_ROW - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_ROW > 1 else 0)
                required_height_for_tickets_pt = (PDF_TICKETS_PER_COL * ticket_height_pt) + \
                                                 ((PDF_TICKETS_PER_COL - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_COL > 1 else 0)

                if required_width_for_tickets_pt > page_content_width_pt:
                    print(f"Warning: Calculated width ({required_width_for_tickets_pt:.2f}pt) for tickets on page exceeds available PDF page content width ({page_content_width_pt:.2f}pt).")
                if required_height_for_tickets_pt > page_content_height_pt:
                    print(f"Warning: Calculated height ({required_height_for_tickets_pt:.2f}pt) for tickets on page exceeds available PDF page content height ({page_content_height_pt:.2f}pt).")


        col_num = ticket_index_on_page % PDF_TICKETS_PER_ROW
        row_num = ticket_index_on_page // PDF_TICKETS_PER_ROW
        
        # Calculate available space on page for content
        page_content_width_pt = pdf.w - 2 * PDF_MARGIN_PT
        # Calculate total width of all tickets and spacing in a row
        total_width_of_row_pt = (PDF_TICKETS_PER_ROW * ticket_width_pt) + \
                                ((PDF_TICKETS_PER_ROW - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_ROW > 1 else 0)
        
        # Calculate horizontal offset to center the block of tickets
        x_offset_for_centering_pt = (page_content_width_pt - total_width_of_row_pt) / 2
        
        x_pt = PDF_MARGIN_PT + x_offset_for_centering_pt + col_num * (ticket_width_pt + PDF_SPACING_PT)
        y_pt = PDF_MARGIN_PT + row_num * (ticket_height_pt + PDF_SPACING_PT) # Vertical centering could be added similarly if desired

        with io.BytesIO() as img_byte_stream:
            pil_image.save(img_byte_stream, format="PNG")
            img_byte_stream.seek(0)
            pdf.image(img_byte_stream, x=x_pt, y=y_pt, w=ticket_width_pt, h=ticket_height_pt, type="PNG")

        ticket_index_on_page += 1
        if ticket_index_on_page >= tickets_per_page:
            ticket_index_on_page = 0

    pdf.output(output_filename, "F")
    print(f"Saved PDF: {output_filename}")


# --- Main Execution (mostly unchanged, uses new scaled constants indirectly) ---
if __name__ == "__main__":
    start_number = int(input("Enter starting ticket number: "))
    end_number = int(input("Enter ending ticket number: "))
    image_file_path = input("Enter path to the image for the ticket center: ") # This is now the main body image
    num_leading_zeros = int(input("Enter number of leading zeros for ticket numbers (e.g., 5 for 00001): "))

    if not (os.path.exists(image_file_path) or image_file_path.strip() == ""):
        print(f"Error: Image file '{image_file_path}' not found. Exiting.")
        exit()
    if image_file_path.strip() == "":
        print("No image path provided. Tickets will be generated without a central image.")
        image_file_path = None

    if FPDF is None:
        print("FPDF2 library is not installed. PDF output is disabled. Exiting.")
        exit()
    
    if start_number > end_number:
        print("Error: Start number cannot be greater than end number. Exiting.")
        exit()

    all_front_pil_images = []
    all_back_pil_images = []

    print("\nGenerating ticket images (using Pillow)...")
    print(f"Target ticket size (WxH): {TICKET_WIDTH_PX}px x {TICKET_HEIGHT_PX}px")
    print(f"Target image height on ticket: {IMAGE_ON_TICKET_HEIGHT_PX}px")
    total_tickets = end_number - start_number + 1
    for count, i in enumerate(range(start_number, end_number + 1)):
        number_string = str(i).zfill(num_leading_zeros)
        if (count + 1) % 10 == 0 or (count + 1) == 1 or (count + 1) == total_tickets :
             print(f"  Creating ticket No. {number_string} ({(count + 1)} of {total_tickets})")

        # IMAGE_ON_TICKET_HEIGHT_PX is now the scaled value
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