﻿using DemeterWeather.Data;
using Microsoft.AspNetCore.Mvc;

namespace DemeterWeather.Controllers
{
    public class LocationsController : Controller
    {
        MongoDbContext database = new MongoDbContext();

        [HttpGet]
        public IActionResult Index(string locationName)
        {
            @ViewData["Location"] = locationName;
            return View();
        }
    }
}
