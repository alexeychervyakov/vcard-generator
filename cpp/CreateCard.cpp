#include <hpdf.h>
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>
#include <opencv2/opencv.hpp>
#include <zint.h>

namespace fs = std::filesystem;

void error_handler(HPDF_STATUS error_no, HPDF_STATUS detail_no, void *user_data) {
    std::cerr << "ERROR: error_no=" << error_no << ", detail_no=" << detail_no << std::endl;
}

std::vector<std::tuple<std::string, std::string, std::string>> load_data(const std::string &csv_file) {
    std::vector<std::tuple<std::string, std::string, std::string>> data;
    std::ifstream file(csv_file);
    if (!file.is_open()) {
        throw std::runtime_error("CSV file not found: " + csv_file);
    }
    std::string line;
    std::getline(file, line); // Skip header
    while (std::getline(file, line)) {
        std::istringstream ss(line);
        std::string name, number, additional_info;
        std::getline(ss, name, ',');
        std::getline(ss, number, ',');
        std::getline(ss, additional_info, ',');
        data.emplace_back(name, number, additional_info);
    }
    return data;
}

std::string calculate_check_digit(const std::string &number) {
    int sum_odd = 0, sum_even = 0;
    for (size_t i = 0; i < number.size(); ++i) {
        int digit = number[i] - '0';
        if (i % 2 == 0) {
            sum_odd += digit;
        } else {
            sum_even += digit;
        }
    }
    int check_digit = (10 - (sum_odd + 3 * sum_even) % 10) % 10;
    return std::to_string(check_digit);
}

void generate_barcode(const std::string &number, const std::string &filename) {
    struct zint_symbol *my_symbol;
    my_symbol = ZBarcode_Create();
    my_symbol->symbology = BARCODE_EANX;
    my_symbol->input_mode = DATA_MODE;
    my_symbol->option_1 = 13; // EAN-13
    std::string full_number = number + calculate_check_digit(number);
    ZBarcode_Encode_and_Print(my_symbol, (unsigned char *)full_number.c_str(), 0, 0);
    ZBarcode_Print(my_symbol, 0);
    ZBarcode_Delete(my_symbol);
}

void create_pdf(const std::string &output_filename, const std::string &csv_file, const std::string &template_path, const std::string &font_path) {
    HPDF_Doc pdf = HPDF_New(error_handler, nullptr);
    if (!pdf) {
        throw std::runtime_error("Failed to create PDF object");
    }
    HPDF_SetCompressionMode(pdf, HPDF_COMP_ALL);
    HPDF_UseUTFEncodings(pdf);
    HPDF_SetCurrentEncoder(pdf, "UTF-8");

    HPDF_Font font = HPDF_GetFont(pdf, font_path.c_str(), "UTF-8");
    if (!font) {
        throw std::runtime_error("Failed to load font: " + font_path);
    }

    auto data = load_data(csv_file);
    HPDF_Page page = HPDF_AddPage(pdf);
    HPDF_Page_SetSize(page, HPDF_PAGE_SIZE_A4, HPDF_PAGE_PORTRAIT);

    for (const auto &[name, number, additional_info] : data) {
        // Draw text and barcode on the PDF page
        HPDF_Page_BeginText(page);
        HPDF_Page_SetFontAndSize(page, font, 24);
        HPDF_Page_TextOut(page, 50, 750, name.c_str());
        HPDF_Page_EndText(page);

        std::string barcode_filename = "barcode_" + number + ".png";
        generate_barcode(number, barcode_filename);
        HPDF_Image barcode_image = HPDF_LoadPngImageFromFile(pdf, barcode_filename.c_str());
        HPDF_Page_DrawImage(page, barcode_image, 50, 700, 100, 50);
        fs::remove(barcode_filename);
    }

    HPDF_SaveToFile(pdf, output_filename.c_str());
    HPDF_Free(pdf);
}

int main() {
    try {
        std::string output_filename = "cards.pdf";
        std::string csv_file = "data/name and numbers.csv";
        std::string template_path = "data/vcard.face.png";
        std::string font_path = "data/font.ttf";
        create_pdf(output_filename, csv_file, template_path, font_path);
    } catch (const std::exception &e) {
        std::cerr << "An error occurred: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}